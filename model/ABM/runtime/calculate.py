#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
calculate.py

承接 test.py（ABM 输出）与 final_two.py / model_GBM.py / model_GAN.py 的结果，
输出三种模型（ABM/GBM/GAN）统一对比指标到：

    simulated_result/<code>/cal_all_compare_metrics.csv

输入承接规则（固定）：
1) 真实价格：{market}_stock/<code>.csv （必须存在）
2) ABM价格：simulated_result/<code>/mid_price.csv（建议存在）
3) GBM价格：{market}_result/<code>/gbm_mid_price.csv（可选）
4) GAN价格：{market}_result/<code>/gan_mid_price.csv（可选）
5) 订单簿：优先 simulated_result/<code>/order_book_reuse.csv，
          若不存在则回退 {market}_result/<code>/order_book_reuse.csv，
          都不存在时量价/深度指标填 NaN，不影响其它指标。
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from scipy.stats import wasserstein_distance, entropy, kurtosis, skew, pearsonr
from sklearn.metrics import mean_squared_error
from statsmodels.tsa.stattools import acf
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import Dataset, DataLoader
    TORCH_AVAILABLE = True
except Exception:
    torch = None
    nn = None
    optim = None

    class Dataset:  # type: ignore[override]
        pass

    class DataLoader:  # type: ignore[override]
        pass

    TORCH_AVAILABLE = False

from loss_function import hill_estimator, calculate_annual_vol, price_to_return, price_to_daily_return


# -----------------------------
# GBM/GAN 生成模块（可选）
# -----------------------------
def estimate_gbm_parameters(prices: np.ndarray, dates: Optional[pd.Series] = None) -> tuple[float, float]:
    log_returns = np.diff(np.log(prices))
    log_returns = log_returns[~np.isnan(log_returns)]
    if len(log_returns) == 0:
        raise ValueError("无法从价格序列计算对数收益率")

    mean_log_return = np.mean(log_returns)
    std_log_return = np.std(log_returns)

    if dates is not None:
        try:
            date_series = pd.to_datetime(dates)
            time_diffs = date_series.diff().dropna()
            avg_diff_days = time_diffs.mean().total_seconds() / (24 * 3600)
            if avg_diff_days < 0.1:
                periods_per_day = 1 / avg_diff_days if avg_diff_days > 0 else 240
                periods_per_year = 252 * periods_per_day
            elif avg_diff_days < 1.5:
                periods_per_year = 252
            else:
                periods_per_year = 52
        except Exception:
            periods_per_year = 252
    else:
        periods_per_year = 252

    mu = mean_log_return * periods_per_year
    sigma = std_log_return * np.sqrt(periods_per_year)
    return float(mu), float(sigma)


def simulate_gbm(S0: float, mu: float, sigma: float, n_steps: int, dt: float = 1.0 / 252) -> np.ndarray:
    np.random.seed(42)
    random_shocks = np.random.normal(0, 1, n_steps)
    prices = np.zeros(n_steps + 1)
    prices[0] = S0
    drift = (mu - 0.5 * sigma**2) * dt
    diffusion = sigma * np.sqrt(dt)
    for i in range(n_steps):
        prices[i + 1] = prices[i] * np.exp(drift + diffusion * random_shocks[i])
    return prices


def run_gbm_model(code: str, market: str, stock_root: Path, model_root: Path) -> bool:
    try:
        stock_file = stock_root / f"{code}.csv"
        if not stock_file.exists():
            print(f"[{code}] [WARN] GBM跳过：未找到股票文件 {stock_file}")
            return False

        df_true = pd.read_csv(stock_file)
        true_prices = df_true["close"].astype(float).values
        if len(true_prices) == 0:
            print(f"[{code}] [WARN] GBM跳过：价格序列为空")
            return False

        mu, sigma = estimate_gbm_parameters(true_prices, df_true.get("date"))
        gbm_prices = simulate_gbm(true_prices[0], mu, sigma, len(true_prices) - 1)
        gbm_prices = gbm_prices[: len(true_prices)]

        result_dir = model_root / code
        result_dir.mkdir(parents=True, exist_ok=True)
        timestamps = df_true["date"].values if "date" in df_true else [f"step_{i}" for i in range(len(gbm_prices))]
        pd.DataFrame({"Timestamp": timestamps, "Price": gbm_prices}).to_csv(
            result_dir / "gbm_mid_price.csv", index=False, encoding="utf-8"
        )
        print(f"[{code}] [OK] GBM生成完成")
        return True
    except Exception as exc:
        print(f"[{code}] [ERROR] GBM生成失败：{exc}")
        return False


class PriceDataset(Dataset):
    def __init__(self, prices: np.ndarray, sequence_length: int = 100):
        self.prices = prices
        self.sequence_length = sequence_length
        self.price_min = prices.min()
        self.price_max = prices.max()
        self.normalized_prices = (prices - self.price_min) / (self.price_max - self.price_min + 1e-8)

    def denormalize(self, normalized: np.ndarray) -> np.ndarray:
        return normalized * (self.price_max - self.price_min) + self.price_min

    def __len__(self) -> int:
        return max(1, len(self.prices) - self.sequence_length)

    def __getitem__(self, idx: int) -> torch.FloatTensor:
        sequence = self.normalized_prices[idx : idx + self.sequence_length]
        return torch.FloatTensor(sequence)


class Generator(nn.Module if TORCH_AVAILABLE else object):
    def __init__(self, noise_dim: int = 100, hidden_dim: int = 256, output_dim: int = 100):
        super().__init__()
        self.noise_dim = noise_dim
        self.fc = nn.Sequential(
            nn.Linear(noise_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim * 2),
            nn.ReLU(),
            nn.Linear(hidden_dim * 2, hidden_dim * 4),
            nn.ReLU(),
            nn.Linear(hidden_dim * 4, output_dim),
            nn.Tanh(),
        )

    def forward(self, noise: torch.Tensor) -> torch.Tensor:
        return self.fc(noise)


class Discriminator(nn.Module if TORCH_AVAILABLE else object):
    def __init__(self, input_dim: int = 100, hidden_dim: int = 256):
        super().__init__()
        self.fc = nn.Sequential(
            nn.Linear(input_dim, hidden_dim * 4),
            nn.LeakyReLU(0.2),
            nn.Dropout(0.3),
            nn.Linear(hidden_dim * 4, hidden_dim * 2),
            nn.LeakyReLU(0.2),
            nn.Dropout(0.3),
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.LeakyReLU(0.2),
            nn.Linear(hidden_dim, 1),
            nn.Sigmoid(),
        )

    def forward(self, sequence: torch.Tensor) -> torch.Tensor:
        return self.fc(sequence)


def train_gan(
    dataset: PriceDataset,
    generator: Generator,
    discriminator: Discriminator,
    epochs: int = 50,
    batch_size: int = 32,
    lr: float = 0.0002,
    device: str = "cpu",
) -> Generator:
    generator, discriminator = generator.to(device), discriminator.to(device)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
    optimizer_g = optim.Adam(generator.parameters(), lr=lr, betas=(0.5, 0.999))
    optimizer_d = optim.Adam(discriminator.parameters(), lr=lr, betas=(0.5, 0.999))
    criterion = nn.BCELoss()

    for _ in range(epochs):
        for real_sequences in dataloader:
            real_sequences = real_sequences.to(device)
            bsz = real_sequences.size(0)
            real_labels = torch.ones(bsz, 1).to(device)
            fake_labels = torch.zeros(bsz, 1).to(device)

            optimizer_d.zero_grad()
            real_output = discriminator(real_sequences)
            loss_d_real = criterion(real_output, real_labels)
            noise = torch.randn(bsz, generator.noise_dim).to(device)
            fake_sequences = generator(noise)
            loss_d_fake = criterion(discriminator(fake_sequences.detach()), fake_labels)
            ((loss_d_real + loss_d_fake) / 2).backward()
            optimizer_d.step()

            optimizer_g.zero_grad()
            noise = torch.randn(bsz, generator.noise_dim).to(device)
            fake_sequences = generator(noise)
            loss_g = criterion(discriminator(fake_sequences), real_labels)
            loss_g.backward()
            optimizer_g.step()

    return generator


def generate_sequence(
    generator: Generator,
    dataset: PriceDataset,
    target_length: int,
    noise_dim: int = 100,
    device: str = "cpu",
) -> np.ndarray:
    generator.eval()
    generated_sequences: List[np.ndarray] = []
    with torch.no_grad():
        segments = (target_length // dataset.sequence_length) + 1
        for _ in range(segments):
            noise = torch.randn(1, noise_dim).to(device)
            sequence = generator(noise).cpu().numpy()[0]
            generated_sequences.append(sequence)
    full_sequence = np.concatenate(generated_sequences)[:target_length]
    return dataset.denormalize(full_sequence)


def run_gan_model(
    code: str,
    market: str,
    stock_root: Path,
    model_root: Path,
    gan_epochs: int = 50,
) -> bool:
    if not TORCH_AVAILABLE:
        print(f"[{code}] [WARN] GAN跳过：未安装 torch")
        return False
    try:
        stock_file = stock_root / f"{code}.csv"
        if not stock_file.exists():
            print(f"[{code}] [WARN] GAN跳过：未找到股票文件 {stock_file}")
            return False

        df_true = pd.read_csv(stock_file)
        true_prices = df_true["close"].astype(float).values
        if len(true_prices) == 0:
            print(f"[{code}] [WARN] GAN跳过：价格序列为空")
            return False

        device = "cuda" if torch.cuda.is_available() else "cpu"
        seq_len = max(10, min(100, len(true_prices) // 10))
        dataset = PriceDataset(true_prices, sequence_length=seq_len)
        generator = Generator(noise_dim=100, hidden_dim=256, output_dim=seq_len)
        discriminator = Discriminator(input_dim=seq_len, hidden_dim=256)
        batch_size = max(1, min(32, len(dataset) // 4))

        trained_generator = train_gan(
            dataset,
            generator,
            discriminator,
            epochs=gan_epochs,
            batch_size=batch_size,
            device=device,
        )
        gan_prices = generate_sequence(trained_generator, dataset, len(true_prices), noise_dim=100, device=device)
        if gan_prices.min() < 0:
            gan_prices = gan_prices - gan_prices.min() + true_prices.min() * 0.5
        gan_prices = gan_prices[: len(true_prices)]

        result_dir = model_root / code
        result_dir.mkdir(parents=True, exist_ok=True)
        timestamps = df_true["date"].values if "date" in df_true else [f"step_{i}" for i in range(len(gan_prices))]
        pd.DataFrame({"Timestamp": timestamps, "Price": gan_prices}).to_csv(
            result_dir / "gan_mid_price.csv", index=False, encoding="utf-8"
        )
        print(f"[{code}] [OK] GAN生成完成")
        return True
    except Exception as exc:
        print(f"[{code}] [ERROR] GAN生成失败：{exc}")
        return False


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
) -> Dict[str, float]:
    return {
        "code": code,
        "model": model_name,
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
    gan_epochs: int = 50,
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

    if generate_models:
        run_gbm_model(code, market, stock_root, model_root)
        run_gan_model(code, market, stock_root, model_root, gan_epochs=gan_epochs)

    abm_dir = resolve_result_dir(abm_root, code)
    model_dir = model_root / code

    abm_price = read_price_file(abm_dir / "mid_price.csv")
    gbm_price = read_price_file(model_dir / "gbm_mid_price.csv")
    gan_price = read_price_file(model_dir / "gan_mid_price.csv")

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
        f"gbm:{'[OK]' if gbm_price is not None else '[MISS]'} gan:{'[OK]' if gan_price is not None else '[MISS]'} "
        f"order:{order_source}"
    )

    results: List[Dict[str, float]] = []

    if abm_price is not None:
        n = min(len(true_prices), len(abm_price))
        results.append(evaluate_model(true_prices[:n], abm_price[:n], order_df, "ABM", code))
    if gbm_price is not None:
        n = min(len(true_prices), len(gbm_price))
        results.append(evaluate_model(true_prices[:n], gbm_price[:n], order_df, "GBM", code))
    if gan_price is not None:
        n = min(len(true_prices), len(gan_price))
        results.append(evaluate_model(true_prices[:n], gan_price[:n], order_df, "GAN", code))

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
        description="一键承接 ABM 并生成 GBM/GAN + 对比评估（默认自动批量）"
    )
    parser.add_argument("--market", default="SM", help="市场前缀，默认 SM")
    parser.add_argument("--code", default=None, help="可选：单股票代码；不传则按 simulated_result/* 批量")
    parser.add_argument("--abm-root", default="simulated_result", help="ABM 输出根目录（默认 simulated_result）")
    parser.add_argument("--stock-root", default=None, help="真实数据目录，默认 {market}_stock")
    parser.add_argument("--model-root", default=None, help="GBM/GAN 输出目录，默认 {market}_result")
    # 默认开启模型生成，实现“直接运行一次性自动生成”
    parser.add_argument(
        "--generate-models",
        dest="generate_models",
        action="store_true",
        default=True,
        help="先生成 GBM/GAN，再做评估（默认开启）",
    )
    parser.add_argument(
        "--no-generate-models",
        dest="generate_models",
        action="store_false",
        help="只评估现有结果，不重新生成 GBM/GAN",
    )
    parser.add_argument("--gan-epochs", type=int, default=50, help="GAN 训练轮数（默认50）")
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
                gan_epochs=args.gan_epochs,
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

