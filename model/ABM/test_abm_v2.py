import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from model.ABM.instance import ABM_V2_MODEL_INSTANCE
from paradigm.model import ModelEnum, load_model_args


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test for RappaExecutor ABM_V2")
    parser.add_argument("--input-csv", required=True, help="Path to standardized single-stock CSV")
    parser.add_argument("--task-sign", required=True, help="Task sign used under meta/<sign>/0")
    parser.add_argument("--task-hash", default="ABM_V2_SMOKE", help="Slot hash used for commit metadata")
    parser.add_argument("--expected-code", required=True, help="Expected normalized output code directory")
    parser.add_argument("--market", default="SM", help="Evaluation market name")
    parser.add_argument("--horizon", type=int, default=3, help="Prediction horizon")
    parser.add_argument("--epochs", type=int, default=1, help="ABM calibration epochs for smoke test")
    parser.add_argument("--max-rows", type=int, default=500, help="Row cap for smoke test runtime")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sample_csv = Path(args.input_csv).resolve()
    if not sample_csv.exists():
        raise FileNotFoundError(f"Sample csv not found: {sample_csv}")

    model_args = load_model_args(ModelEnum.ABM_V2, is_cuda=False)
    instance = ABM_V2_MODEL_INSTANCE(model_args=model_args)

    output = instance.generate_output(
        1,
        {
            "__slot_hash": args.task_hash,
            "__slot_sign": args.task_sign,
            "input_csv": str(sample_csv),
            "predict": {
                "enabled": True,
                "method": "auto",
                "horizon": args.horizon,
            },
            "abm": {
                "epochs": args.epochs,
                "learning_rate": 0.01,
                "epsilon": 0.001,
                "max_rows": args.max_rows,
                "seed_count": 1,
                "bootstrap_samples": 10,
                "patience": 1,
                "structural_params": {
                    "N_FT": 20,
                    "N_LMT": 20,
                    "N_SMT": 20,
                    "N_NT": 20,
                    "S_FT": 1,
                    "ALPHA_L": 0.001,
                    "ALPHA_S": 0.9,
                },
            },
            "evaluation": {
                "market": args.market,
                "generate_models": False,
                "vrnn_epochs": 1,
                "timegan_epochs": 1,
                "min_deep_samples": 200,
                "allow_fallback": True,
            },
        },
    )

    manifest = output.output
    print("ABM_V2 manifest rows:", len(manifest))
    print(manifest[["artifact_name", "relative_path", "size_bytes"]].head(25).to_string(index=False))

    required = {
        "runtime_params/params.json",
        "outputs/predict/predict_fv.csv",
        "outputs/predict/predict_fv_meta.json",
        f"outputs/abm/{args.expected_code}/cal_all_compare_metrics.csv",
        f"outputs/abm/{args.expected_code}/mid_price.csv",
        "logs/pipeline.stdout.log",
        "logs/pipeline.stderr.log",
    }
    got = set(manifest["relative_path"].tolist())
    missing = sorted(required - got)
    if missing:
        raise AssertionError(f"ABM_V2 smoke test missing artifacts: {missing}")

    task_dir = PROJECT_ROOT / "meta" / args.task_sign / "0"
    print("Task dir:", task_dir)
    print("Smoke test passed.")


if __name__ == "__main__":
    main()
