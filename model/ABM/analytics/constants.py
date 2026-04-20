TRADER_TYPE_ORDER = [
    ("Fundamental_Trader", "基本面"),
    ("Long_term_Momentum_Trader", "长动量"),
    ("Short_term_Momentum_Trader", "短动量"),
    ("Noise_Trader", "噪声"),
]

TRADER_TYPES = [item[0] for item in TRADER_TYPE_ORDER]

PERFORMANCE_TABLE_ROWS = [
    {"indicator": "Mean (均值)", "true_key": "mean_true", "sim_key": "mean_sim", "diff_mode": "relative_pct"},
    {"indicator": "Std Dev (标准差)", "true_key": "std_true", "sim_key": "std_sim", "diff_mode": "relative_pct"},
    {"indicator": "CV (变异系数)", "true_key": "cv_true", "sim_key": "cv_sim", "diff_mode": "relative_pct"},
    {"indicator": "Kurtosis (峰度)", "true_key": "kurt_true", "sim_key": "kurt_sim", "diff_mode": "relative_pct"},
    {"indicator": "Skewness (偏度)", "true_key": "skew_true", "sim_key": "skew_sim", "diff_mode": "relative_pct"},
    {"indicator": "Pearson Corr", "true_value": 1.0, "sim_key": "pearson_corr", "diff_mode": "relative_pct"},
    {"indicator": "ACF Abs Diff", "true_value": 0.0, "sim_key": "acf_abs_mean_diff", "diff_mode": "absolute"},
    {"indicator": "Depth Ratio", "true_value": 1.0, "sim_key": "depth_ratio", "diff_mode": "relative_pct"},
    {"indicator": "Volume Mean", "sim_key": "volume_mean", "diff_mode": "none"},
    {"indicator": "Wasserstein", "true_value": 0.0, "sim_key": "wasserstein", "diff_mode": "absolute"},
    {"indicator": "KL Divergence", "true_value": 0.0, "sim_key": "kl_divergence", "diff_mode": "absolute"},
]

RADAR_INDICATORS = [
    {"name": "风险收益\n(Risk/Return)", "max": 100},
    {"name": "分布特征\n(Distribution)", "max": 100},
    {"name": "形状与轨迹\n(Trajectory)", "max": 100},
    {"name": "量价行为\n(Price/Volume)", "max": 100},
]

CRASH_RISK_BANDS = [
    {"label": "低风险", "range": [0, 0.3]},
    {"label": "中风险", "range": [0.3, 0.6]},
    {"label": "高风险", "range": [0.6, 1.0]},
]
