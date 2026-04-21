#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
calculate.py

承接 test.py（ABM 输出）与基准模型结果，
输出三种模型（ABM/VRNN/TimeGAN）统一对比指标到：

    simulated_result/<code>/cal_all_compare_metrics.csv

输入承接规则（固定）：
1) 真实价格：{market}_stock/<code>.csv （必须存在）
2) ABM价格：simulated_result/<code>/mid_price.csv（建议存在）
3) VRNN价格：{market}_result/<code>/vrnn_mid_price.csv（可选）
4) TimeGAN价格：{market}_result/<code>/timegan_mid_price.csv（可选）
5) 订单簿：优先 simulated_result/<code>/order_book_reuse.csv，
          若不存在则回退 {market}_result/<code>/order_book_reuse.csv，
          都不存在时量价/深度指标填 NaN，不影响其它指标。
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.stats import wasserstein_distance, entropy, kurtosis, skew, pearsonr
from sklearn.metrics import mean_squared_error
from statsmodels.tsa.stattools import acf
try:
    import tensorflow as tf
    from tensorflow.keras import layers, models
    from tensorflow.keras import backend as K
    TF_AVAILABLE = True
except Exception:
    tf = None
    layers = None
    models = None
    K = None
    TF_AVAILABLE = False

from loss_function import hill_estimator, calculate_annual_vol, price_to_return, price_to_daily_return


# -----------------------------
# VRNN/TimeGAN 生成模块（可选）
# -----------------------------
def _create_sequences(data: np.ndarray, seq_len: int) -> np.ndarray:
    if len(data) <= seq_len:
        return np.empty((0, seq_len, 1), dtype=np.float32)
    return np.array([data[i : i + seq_len] for i in range(len(data) - seq_len)], dtype=np.float32).reshape(-1, seq_len, 1)


def _safe_random_walk(prices: np.ndarray, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    if len(prices) <= 1:
        return prices.copy()
    rets = np.diff(np.log(np.clip(prices, 1e-8, None)))
    mu = float(np.mean(rets)) if len(rets) else 0.0
    sigma = float(np.std(rets)) if len(rets) else 0.01
    sim = [float(prices[0])]
    for _ in range(len(prices) - 1):
        sim.append(sim[-1] * np.exp(mu + sigma * rng.normal()))
    return np.array(sim, dtype=float)


def _write_model_price_file(model_root: Path, code: str, file_name: str, timestamps, prices: np.ndarray) -> None:
    result_dir = model_root / code
    result_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"Timestamp": timestamps, "Price": prices}).to_csv(
        result_dir / file_name, index=False, encoding="utf-8"
    )


def _fallback_model_from_exception(
    code: str,
    stock_root: Path,
    model_root: Path,
    file_name: str,
    seed: int,
    label: str,
    exc: Exception,
    allow_fallback: bool,
) -> Tuple[bool, str]:
    if not allow_fallback:
        print(f"[{code}] [ERROR] {label}生成失败：{exc}")
        return False, "error_exception"

    try:
        stock_file = stock_root / f"{code}.csv"
        if not stock_file.exists():
            print(f"[{code}] [ERROR] {label}生成失败且无法回退：未找到股票文件 {stock_file}，原错误：{exc}")
            return False, "error_exception_missing_stock_file"

        df_true = pd.read_csv(stock_file)
        true_prices = df_true["close"].astype(float).values
        fallback_prices = _safe_random_walk(true_prices, seed=seed)
        timestamps = df_true["date"].values if "date" in df_true else [f"step_{i}" for i in range(len(fallback_prices))]
        _write_model_price_file(model_root, code, file_name, timestamps, fallback_prices[: len(true_prices)])
        print(f"[{code}] [WARN] {label}生成失败，已回退为随机游走近似，mode=fallback_exception，原错误：{exc}")
        return True, "fallback_exception"
    except Exception as fallback_exc:
        print(f"[{code}] [ERROR] {label}生成失败且回退失败：{fallback_exc}，原错误：{exc}")
        return False, "error_exception_fallback_failed"


def run_vrnn_model(
    code: str,
    market: str,
    stock_root: Path,
    model_root: Path,
    vrnn_epochs: int = 50,
    min_deep_samples: int = 50,
    allow_fallback: bool = True,
) -> Tuple[bool, str]:
    try:
        stock_file = stock_root / f"{code}.csv"
        if not stock_file.exists():
            print(f"[{code}] [WARN] VRNN跳过：未找到股票文件 {stock_file}")
            return False, "missing_stock_file"

        df_true = pd.read_csv(stock_file)
        true_prices = df_true["close"].astype(float).values
        mode = "deep"
        if not TF_AVAILABLE:
            if not allow_fallback:
                print(f"[{code}] [WARN] 未安装 tensorflow，VRNN跳过（禁用回退）")
                return False, "skip_tf_unavailable"
            print(f"[{code}] [WARN] 未安装 tensorflow，VRNN回退为随机游走近似")
            vrnn_prices = _safe_random_walk(true_prices, seed=42)
            mode = "fallback_tf_unavailable"
        elif len(true_prices) < min_deep_samples:
            if not allow_fallback:
                print(f"[{code}] [WARN] VRNN样本不足({len(true_prices)}<{min_deep_samples})，跳过（禁用回退）")
                return False, "skip_samples_too_short"
            print(f"[{code}] [WARN] VRNN样本过短，回退随机游走")
            vrnn_prices = _safe_random_walk(true_prices)
            mode = "fallback_samples_too_short"
        else:
            tf.keras.backend.clear_session()
            tf.random.set_seed(42)
            np.random.seed(42)

            returns = np.diff(true_prices) / np.clip(true_prices[:-1], 1e-8, None)
            r_mean = float(np.mean(returns))
            r_std = float(np.std(returns) + 1e-8)
            returns_norm = ((returns - r_mean) / r_std).astype(np.float32)

            seq_len = max(10, min(30, len(returns_norm) // 20))
            train_seq = _create_sequences(returns_norm, seq_len)
            if len(train_seq) == 0:
                if not allow_fallback:
                    print(f"[{code}] [WARN] VRNN可训练序列为空，跳过（禁用回退）")
                    return False, "skip_empty_train_seq"
                vrnn_prices = _safe_random_walk(true_prices)
                mode = "fallback_empty_train_seq"
            else:
                inputs = layers.Input(shape=(seq_len, 1))
                h = layers.LSTM(64, return_sequences=True)(inputs)
                h = layers.LSTM(32, return_sequences=False)(h)
                z_mean = layers.Dense(8)(h)
                z_log_var = layers.Dense(8)(h)

                def sampling(args):
                    z_mu, z_lv = args
                    eps = K.random_normal(shape=(K.shape(z_mu)[0], 8))
                    return z_mu + K.exp(0.5 * z_lv) * eps

                z = layers.Lambda(sampling)([z_mean, z_log_var])
                dec = layers.RepeatVector(seq_len)(z)
                dec = layers.LSTM(32, return_sequences=True)(dec)
                outputs = layers.TimeDistributed(layers.Dense(1))(dec)

                model = models.Model(inputs, outputs)
                beta = 0.2
                recon = tf.reduce_mean(tf.square(inputs - outputs))
                kl = -0.5 * tf.reduce_mean(1 + z_log_var - tf.square(z_mean) - tf.exp(z_log_var))
                model.add_loss(recon + beta * kl)
                model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3))
                model.fit(train_seq, train_seq, epochs=max(5, vrnn_epochs), batch_size=64, verbose=0)

                gen_rets = []
                window = returns_norm[-seq_len:].reshape(1, seq_len, 1)
                for _ in range(len(true_prices) - 1):
                    pred_seq = model.predict(window, verbose=0)[0, :, 0]
                    next_r = float(pred_seq[-1])
                    gen_rets.append(next_r)
                    window = np.roll(window, -1, axis=1)
                    window[0, -1, 0] = next_r

                gen_rets = np.array(gen_rets) * r_std + r_mean
                vrnn_prices = np.empty(len(true_prices), dtype=float)
                vrnn_prices[0] = float(true_prices[0])
                for i, r in enumerate(gen_rets, start=1):
                    vrnn_prices[i] = max(0.01, vrnn_prices[i - 1] * (1.0 + float(r)))

        timestamps = df_true["date"].values if "date" in df_true else [f"step_{i}" for i in range(len(vrnn_prices))]
        _write_model_price_file(model_root, code, "vrnn_mid_price.csv", timestamps, vrnn_prices[: len(true_prices)])
        print(f"[{code}] [OK] VRNN生成完成（写入 vrnn_mid_price.csv），mode={mode}")
        return True, mode
    except Exception as exc:
        return _fallback_model_from_exception(
            code,
            stock_root,
            model_root,
            "vrnn_mid_price.csv",
            seed=42,
            label="VRNN",
            exc=exc,
            allow_fallback=allow_fallback,
        )


def run_timegan_model(
    code: str,
    market: str,
    stock_root: Path,
    model_root: Path,
    timegan_epochs: int = 50,
    min_deep_samples: int = 50,
    allow_fallback: bool = True,
) -> Tuple[bool, str]:
    try:
        stock_file = stock_root / f"{code}.csv"
        if not stock_file.exists():
            print(f"[{code}] [WARN] TimeGAN跳过：未找到股票文件 {stock_file}")
            return False, "missing_stock_file"

        df_true = pd.read_csv(stock_file)
        true_prices = df_true["close"].astype(float).values
        mode = "deep"
        if not TF_AVAILABLE:
            if not allow_fallback:
                print(f"[{code}] [WARN] 未安装 tensorflow，TimeGAN跳过（禁用回退）")
                return False, "skip_tf_unavailable"
            print(f"[{code}] [WARN] 未安装 tensorflow，TimeGAN回退为随机游走近似")
            timegan_prices = _safe_random_walk(true_prices, seed=99)
            mode = "fallback_tf_unavailable"
        elif len(true_prices) < min_deep_samples:
            if not allow_fallback:
                print(f"[{code}] [WARN] TimeGAN样本不足({len(true_prices)}<{min_deep_samples})，跳过（禁用回退）")
                return False, "skip_samples_too_short"
            print(f"[{code}] [WARN] TimeGAN样本过短，回退随机游走")
            timegan_prices = _safe_random_walk(true_prices)
            mode = "fallback_samples_too_short"
        else:
            tf.keras.backend.clear_session()
            tf.random.set_seed(42)
            np.random.seed(42)

            p_mean = float(np.mean(true_prices))
            p_std = float(np.std(true_prices) + 1e-8)
            norm_prices = ((true_prices - p_mean) / p_std).astype(np.float32)

            seq_len = max(10, min(30, len(norm_prices) // 20))
            train_seq = _create_sequences(norm_prices, seq_len)
            if len(train_seq) == 0:
                if not allow_fallback:
                    print(f"[{code}] [WARN] TimeGAN可训练序列为空，跳过（禁用回退）")
                    return False, "skip_empty_train_seq"
                timegan_prices = _safe_random_walk(true_prices)
                mode = "fallback_empty_train_seq"
            else:
                latent_dim = 32
                generator = models.Sequential(
                    [
                        layers.Input(shape=(seq_len, latent_dim)),
                        layers.LSTM(64, activation="tanh", return_sequences=True),
                        layers.Dense(32, activation="relu"),
                        layers.Dense(1, activation="linear"),
                    ]
                )
                discriminator = models.Sequential(
                    [
                        layers.Input(shape=(seq_len, 1)),
                        layers.LSTM(64, activation="tanh"),
                        layers.Dense(32, activation="relu"),
                        layers.Dense(1, activation="sigmoid"),
                    ]
                )
                discriminator.compile(
                    optimizer=tf.keras.optimizers.Adam(1e-3),
                    loss="binary_crossentropy",
                    metrics=["accuracy"],
                )
                discriminator.trainable = False

                gan = models.Sequential([generator, discriminator])
                gan.compile(optimizer=tf.keras.optimizers.Adam(1e-3), loss="binary_crossentropy")

                batch_size = min(64, max(8, len(train_seq) // 4))
                half = max(1, batch_size // 2)
                valid = np.ones((batch_size, 1), dtype=np.float32)
                fake = np.zeros((batch_size, 1), dtype=np.float32)

                for _ in range(max(5, timegan_epochs)):
                    idx = np.random.randint(0, len(train_seq), half)
                    real_batch = train_seq[idx]
                    noise = np.random.normal(0, 1, (half, seq_len, latent_dim)).astype(np.float32)
                    fake_batch = generator.predict(noise, verbose=0)

                    discriminator.trainable = True
                    discriminator.train_on_batch(real_batch, valid[:half])
                    discriminator.train_on_batch(fake_batch, fake[:half])

                    discriminator.trainable = False
                    noise = np.random.normal(0, 1, (batch_size, seq_len, latent_dim)).astype(np.float32)
                    gan.train_on_batch(noise, valid)

                segments = (len(true_prices) // seq_len) + 1
                generated = []
                for _ in range(segments):
                    noise = np.random.normal(0, 1, (1, seq_len, latent_dim)).astype(np.float32)
                    seg = generator.predict(noise, verbose=0)[0, :, 0]
                    generated.extend(seg.tolist())
                generated = np.array(generated[: len(true_prices)], dtype=float)
                timegan_prices = generated * p_std + p_mean
                timegan_prices = np.maximum(timegan_prices, 0.01)

        timestamps = df_true["date"].values if "date" in df_true else [f"step_{i}" for i in range(len(timegan_prices))]
        _write_model_price_file(model_root, code, "timegan_mid_price.csv", timestamps, timegan_prices[: len(true_prices)])
        print(f"[{code}] [OK] TimeGAN生成完成（写入 timegan_mid_price.csv），mode={mode}")
        return True, mode
    except Exception as exc:
        return _fallback_model_from_exception(
            code,
            stock_root,
            model_root,
            "timegan_mid_price.csv",
            seed=99,
            label="TimeGAN",
            exc=exc,
            allow_fallback=allow_fallback,
        )


def kl_divergence(p: np.ndarray, q: np.ndarray, bins: int = 100, eps: float = 1e-10) -> float:
    min_val = min(np.min(p), np.min(q))
    max_val = max(np.max(p), np.max(q))
    if min_val == max_val:
        return 0.0
    hist1, bin_edges = np.histogram(p, bins=bins, range=(min_val, max_val), density=True)
    hist2, _ = np.histogram(q, bins=bin_edges, density=True)
    hist1 = np.clip(hist1, eps, None)
    hist2 = np.clip(hist2, eps, None)
    return float(entropy(hist1, hist2))


def calc_basic_stats(true_prices: np.ndarray, sim_prices: np.ndarray) -> Dict[str, float]:
    mean_true, mean_sim = np.mean(true_prices), np.mean(sim_prices)
    std_true, std_sim = np.std(true_prices), np.std(sim_prices)
    cv_true = std_true / mean_true if mean_true else np.nan
    cv_sim = std_sim / mean_sim if mean_sim else np.nan
    return {
        "mean_true": float(mean_true),
        "mean_sim": float(mean_sim),
        "std_true": float(std_true),
        "std_sim": float(std_sim),
        "cv_true": float(cv_true) if not np.isnan(cv_true) else np.nan,
        "cv_sim": float(cv_sim) if not np.isnan(cv_sim) else np.nan,
        "wasserstein": float(wasserstein_distance(true_prices, sim_prices)),
        "kl_divergence": float(kl_divergence(true_prices, sim_prices)),
        "mse": float(mean_squared_error(true_prices, sim_prices)),
        "pearson_corr": float(pearsonr(true_prices, sim_prices)[0]),
    }


def calc_returns_metrics(true_prices: np.ndarray, sim_prices: np.ndarray) -> Dict[str, float]:
    true_ret = np.array(price_to_return(true_prices), dtype=float)
    sim_ret = np.array(price_to_return(sim_prices), dtype=float)
    n = min(len(true_ret), len(sim_ret))
    if n == 0:
        raise ValueError("收益序列为空，无法计算收益相关指标")
    true_ret = true_ret[:n]
    sim_ret = sim_ret[:n]

    k = max(1, int(n * 0.05))
    true_hill = float(hill_estimator(np.abs(true_ret), k))
    sim_hill = float(hill_estimator(np.abs(sim_ret), k))

    true_daily = np.array(price_to_daily_return(true_prices), dtype=float)
    sim_daily = np.array(price_to_daily_return(sim_prices), dtype=float)
    vol_true = float(calculate_annual_vol(true_daily))
    vol_sim = float(calculate_annual_vol(sim_daily))

    acf_diff = np.nan
    if n > 1:
        nlags = min(10, n - 1)
        acf_true = acf(np.abs(true_ret), nlags=nlags, fft=False)
        acf_sim = acf(np.abs(sim_ret), nlags=nlags, fft=False)
        acf_diff = float(np.nanmean(np.abs(acf_true - acf_sim)))

    return {
        "hill_true": true_hill,
        "hill_sim": sim_hill,
        "hill_diff_pct": abs(sim_hill - true_hill) / true_hill * 100 if true_hill else np.nan,
        "annual_vol_true": vol_true,
        "annual_vol_sim": vol_sim,
        "annual_vol_diff_pct": abs(vol_sim - vol_true) / vol_true * 100 if vol_true else np.nan,
        "acf_abs_mean_diff": acf_diff,
        "kurt_true": float(kurtosis(true_ret)),
        "kurt_sim": float(kurtosis(sim_ret)),
        "skew_true": float(skew(true_ret)),
        "skew_sim": float(skew(sim_ret)),
    }


def nan_volume_metrics() -> Dict[str, float]:
    return {
        "price_volume_corr_true": np.nan,
        "price_volume_corr_sim": np.nan,
        "volume_mean": np.nan,
        "volume_std": np.nan,
        "volume_skew": np.nan,
        "volume_kurt": np.nan,
    }


def calc_price_volume(true_prices: np.ndarray, sim_prices: np.ndarray, order_df: Optional[pd.DataFrame]) -> Dict[str, float]:
    if order_df is None or not {"Timestamp", "Volume"}.issubset(order_df.columns):
        return nan_volume_metrics()

    try:
        tmp = order_df.copy()
        tmp["Timestamp"] = pd.to_datetime(tmp["Timestamp"])
        volume = tmp.groupby("Timestamp")["Volume"].sum().sort_index().values
        n = min(len(volume), len(true_prices), len(sim_prices))
        if n <= 2:
            return nan_volume_metrics()

        volume = volume[:n]
        true_ret = np.array(price_to_return(true_prices[:n]), dtype=float)
        sim_ret = np.array(price_to_return(sim_prices[:n]), dtype=float)
        vol_ret = np.array(price_to_return(volume), dtype=float)
        m = min(len(true_ret), len(sim_ret), len(vol_ret))
        if m <= 2:
            return nan_volume_metrics()

        return {
            "price_volume_corr_true": float(pearsonr(true_ret[:m], vol_ret[:m])[0]),
            "price_volume_corr_sim": float(pearsonr(sim_ret[:m], vol_ret[:m])[0]),
            "volume_mean": float(np.mean(volume)),
            "volume_std": float(np.std(volume)),
            "volume_skew": float(skew(volume)),
            "volume_kurt": float(kurtosis(volume)),
        }
    except Exception:
        return nan_volume_metrics()


def calc_depth_stats(order_df: Optional[pd.DataFrame]) -> Dict[str, float]:
    if order_df is None or not {"IsBuy", "Volume"}.issubset(order_df.columns):
        return {"buy_depth": np.nan, "sell_depth": np.nan, "depth_ratio": np.nan}
    try:
        buy_depth = float(order_df.loc[order_df["IsBuy"] == True, "Volume"].sum())
        sell_depth = float(order_df.loc[order_df["IsBuy"] == False, "Volume"].sum())
        ratio = buy_depth / sell_depth if sell_depth else np.nan
        return {"buy_depth": buy_depth, "sell_depth": sell_depth, "depth_ratio": ratio}
    except Exception:
        return {"buy_depth": np.nan, "sell_depth": np.nan, "depth_ratio": np.nan}


def evaluate_model(
    true_prices: np.ndarray,
    sim_prices: np.ndarray,
    order_df: Optional[pd.DataFrame],
    model_name: str,
    code: str,
    runtime_mode: str = "unknown",
) -> Dict[str, float]:
    return {
        "code": code,
        "model": model_name,
        "runtime_mode": runtime_mode,
        **calc_basic_stats(true_prices, sim_prices),
        **calc_returns_metrics(true_prices, sim_prices),
        **calc_price_volume(true_prices, sim_prices, order_df),
        **calc_depth_stats(order_df),
    }


def read_price_file(path: Path) -> Optional[np.ndarray]:
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path)
        if "Price" not in df.columns:
            return None
        return df["Price"].astype(float).values
    except Exception:
        return None


def read_order_file(abm_path: Path, fallback_path: Path) -> Optional[pd.DataFrame]:
    if abm_path.exists():
        try:
            return pd.read_csv(abm_path)
        except Exception:
            return None
    if fallback_path.exists():
        try:
            return pd.read_csv(fallback_path)
        except Exception:
            return None
    return None


def resolve_result_dir(root: Path, code: str) -> Path:
    candidates: List[str] = []
    for value in (code, code.lstrip("0") or "0"):
        if value and value not in candidates:
            candidates.append(value)
    for candidate in candidates:
        path = root / candidate
        if path.exists():
            return path
    return root / code


def run_for_code(
    code: str,
    market: str,
    stock_root: Path,
    model_root: Path,
    abm_root: Path,
    generate_models: bool = False,
    vrnn_epochs: int = 50,
    timegan_epochs: int = 50,
    min_deep_samples: int = 50,
    allow_fallback: bool = True,
) -> bool:
    true_file = stock_root / f"{code}.csv"
    if not true_file.exists():
        print(f"[{code}] [ERROR] 缺少真实数据: {true_file}")
        return False

    try:
        true_prices = pd.read_csv(true_file)["close"].astype(float).values
    except Exception as exc:
        print(f"[{code}] [ERROR] 读取真实价格失败: {exc}")
        return False

    vrnn_mode = "loaded_existing"
    timegan_mode = "loaded_existing"
    vrnn_ok = True
    timegan_ok = True
    if generate_models:
        vrnn_ok, vrnn_mode = run_vrnn_model(
            code,
            market,
            stock_root,
            model_root,
            vrnn_epochs=vrnn_epochs,
            min_deep_samples=min_deep_samples,
            allow_fallback=allow_fallback,
        )
        timegan_ok, timegan_mode = run_timegan_model(
            code,
            market,
            stock_root,
            model_root,
            timegan_epochs=timegan_epochs,
            min_deep_samples=min_deep_samples,
            allow_fallback=allow_fallback,
        )

    abm_dir = resolve_result_dir(abm_root, code)
    model_dir = model_root / code

    abm_price = read_price_file(abm_dir / "mid_price.csv")
    vrnn_price = read_price_file(model_dir / "vrnn_mid_price.csv") if vrnn_ok else None
    timegan_price = read_price_file(model_dir / "timegan_mid_price.csv") if timegan_ok else None

    order_df = read_order_file(
        abm_dir / "order_book_reuse.csv",
        model_dir / "order_book_reuse.csv",
    )
    order_source = "none"
    if (abm_dir / "order_book_reuse.csv").exists():
        order_source = "abm"
    elif (model_dir / "order_book_reuse.csv").exists():
        order_source = "model"

    print(
        f"[{code}] 输入检查 -> true:[OK] abm:{'[OK]' if abm_price is not None else '[MISS]'} "
        f"vrnn:{'[OK]' if vrnn_price is not None else '[MISS]'} timegan:{'[OK]' if timegan_price is not None else '[MISS]'} "
        f"order:{order_source}"
    )

    results: List[Dict[str, float]] = []

    if abm_price is not None:
        n = min(len(true_prices), len(abm_price))
        results.append(evaluate_model(true_prices[:n], abm_price[:n], order_df, "ABM", code, runtime_mode="na"))
    if vrnn_price is not None:
        n = min(len(true_prices), len(vrnn_price))
        results.append(evaluate_model(true_prices[:n], vrnn_price[:n], order_df, "VRNN", code, runtime_mode=vrnn_mode))
    if timegan_price is not None:
        n = min(len(true_prices), len(timegan_price))
        results.append(
            evaluate_model(true_prices[:n], timegan_price[:n], order_df, "TimeGAN", code, runtime_mode=timegan_mode)
        )

    if not results:
        print(f"[{code}] [WARN] 没有可评估模型文件，跳过")
        return False

    out_dir = abm_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "cal_all_compare_metrics.csv"
    out_df = pd.DataFrame(results)
    cols = ["code", "model"] + [c for c in out_df.columns if c not in {"code", "model"}]
    out_df = out_df[cols]
    out_df.to_csv(out_file, index=False, encoding="utf-8-sig")

    model_gen_meta = {
        "code": code,
        "tf_available": bool(TF_AVAILABLE),
        "min_deep_samples": int(min_deep_samples),
        "allow_fallback": bool(allow_fallback),
        "vrnn_mode": vrnn_mode,
        "timegan_mode": timegan_mode,
    }
    pd.Series(model_gen_meta).to_json(out_dir / "model_generation_meta.json", force_ascii=False, indent=2)

    # -------- 分类别输出（按需求拆分）--------
    # 1) 差异类：模型 vs 真实，输出单个差异值
    diff_cols = [
        "code",
        "model",
        "mse",
        "wasserstein",
        "kl_divergence",
        "hill_diff_pct",
        "annual_vol_diff_pct",
        "acf_abs_mean_diff",
    ]
    diff_cols = [c for c in diff_cols if c in out_df.columns]
    diff_df = out_df[diff_cols].copy()
    diff_file = out_dir / "cal_compare_diff_metrics.csv"
    diff_df.to_csv(diff_file, index=False, encoding="utf-8-sig")

    # 2) 水平/形态类：真实统计 vs 模型统计并列展示
    level_cols = [
        "code",
        "model",
        "mean_true",
        "mean_sim",
        "std_true",
        "std_sim",
        "cv_true",
        "cv_sim",
        "hill_true",
        "hill_sim",
        "annual_vol_true",
        "annual_vol_sim",
        "kurt_true",
        "kurt_sim",
        "skew_true",
        "skew_sim",
        "pearson_corr",
    ]
    level_cols = [c for c in level_cols if c in out_df.columns]
    level_df = out_df[level_cols].copy()
    level_file = out_dir / "cal_compare_level_metrics.csv"
    level_df.to_csv(level_file, index=False, encoding="utf-8-sig")

    print(f"[{code}] [OK] 已输出: {out_file}")
    return True


def discover_codes(abm_root: Path, explicit_code: Optional[str]) -> List[str]:
    if explicit_code:
        return [explicit_code]
    if not abm_root.exists():
        return []
    return sorted([p.name for p in abm_root.iterdir() if p.is_dir()])


def main():
    parser = argparse.ArgumentParser(
        description="一键承接 ABM 并生成 VRNN/TimeGAN + 对比评估（默认自动批量）"
    )
    parser.add_argument("--market", default="SM", help="市场前缀，默认 SM")
    parser.add_argument("--code", default=None, help="可选：单股票代码；不传则按 simulated_result/* 批量")
    parser.add_argument("--abm-root", default="simulated_result", help="ABM 输出根目录（默认 simulated_result）")
    parser.add_argument("--stock-root", default=None, help="真实数据目录，默认 {market}_stock")
    parser.add_argument("--model-root", default=None, help="VRNN/TimeGAN 输出目录，默认 {market}_result")
    # 默认开启模型生成，实现“直接运行一次性自动生成”
    parser.add_argument(
        "--generate-models",
        dest="generate_models",
        action="store_true",
        default=True,
        help="先生成 VRNN/TimeGAN，再做评估（默认开启）",
    )
    parser.add_argument(
        "--no-generate-models",
        dest="generate_models",
        action="store_false",
        help="只评估现有结果，不重新生成 VRNN/TimeGAN",
    )
    parser.add_argument("--vrnn-epochs", type=int, default=50, help="VRNN 训练轮数（默认50）")
    parser.add_argument("--timegan-epochs", type=int, default=50, help="TimeGAN 训练轮数（默认50）")
    parser.add_argument("--min-deep-samples", type=int, default=50, help="触发深度模型训练的最小样本长度（默认50）")
    parser.add_argument(
        "--no-fallback",
        dest="allow_fallback",
        action="store_false",
        default=True,
        help="禁用回退近似生成（不满足深度训练条件时对应模型将跳过）",
    )
    args = parser.parse_args()

    market = args.market.upper()
    abm_root = Path(args.abm_root)
    stock_root = Path(args.stock_root) if args.stock_root else Path(f"{market}_stock")
    model_root = Path(args.model_root) if args.model_root else Path(f"{market}_result")

    codes = discover_codes(abm_root, args.code)
    if not codes:
        print("[ERROR] 未发现可处理的 code。请检查 --code 或 simulated_result 子目录。")
        return

    ok = 0
    fail = 0
    for code in codes:
        try:
            if run_for_code(
                code,
                market,
                stock_root,
                model_root,
                abm_root,
                generate_models=args.generate_models,
                vrnn_epochs=args.vrnn_epochs,
                timegan_epochs=args.timegan_epochs,
                min_deep_samples=args.min_deep_samples,
                allow_fallback=args.allow_fallback,
            ):
                ok += 1
            else:
                fail += 1
        except Exception as exc:
            fail += 1
            print(f"[{code}] [ERROR] 评估异常: {exc}")

    print("\n" + "=" * 60)
    print(f"评估完成：成功 {ok}，失败 {fail}，总计 {len(codes)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
