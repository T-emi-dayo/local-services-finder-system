"""Expand the seed goldens into a fixed number of synthetic test goldens."""
import argparse
from pathlib import Path

from dotenv import load_dotenv


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", default="eval/data/goldens_v1.json")
    parser.add_argument("--out-dir", default="eval/data")
    parser.add_argument("--file-name", default="synthetic_tests_v1")
    parser.add_argument("--target-count", type=int, default=50)
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--max-concurrent", type=int, default=2)
    args = parser.parse_args()
    if args.target_count < 1 or args.max_concurrent < 1:
        parser.error("target-count and max-concurrent must be positive")
    if not Path(args.seed).exists():
        parser.error(f"Seed golden file not found: {args.seed}")

    try:
        from deepeval.dataset import EvaluationDataset
        from deepeval.synthesizer import Synthesizer
        from deepeval.synthesizer.config import StylingConfig
    except ImportError as exc:
        raise SystemExit("DeepEval is not installed. Run: pip install -r eval/requirements.txt") from exc

    seed_dataset = EvaluationDataset()
    seed_dataset.add_goldens_from_json_file(file_path=str(Path(args.seed).resolve()))
    seed_goldens = seed_dataset.goldens
    if not seed_goldens:
        parser.error("Seed dataset contains no goldens")
    if any(not getattr(golden, "context", None) for golden in seed_goldens):
        parser.error("Every seed golden must carry its supporting context so generated expected answers stay grounded")
    if args.target_count % len(seed_goldens) != 0:
        parser.error(
            f"target-count ({args.target_count}) must be divisible by seed count ({len(seed_goldens)}) "
            "to avoid generating and discarding paid examples; generate an even seed set or choose a divisible target"
        )

    per_seed = args.target_count // len(seed_goldens)
    print(f"Expanding {len(seed_goldens)} seed goldens to {args.target_count} synthetic test goldens; this makes LLM calls.")
    synthesizer = Synthesizer(
        model=args.model,
        async_mode=True,
        max_concurrent=args.max_concurrent,
        cost_tracking=True,
        styling_config=StylingConfig(
            task="Create realistic test queries for a local services finder in Nigeria.",
            scenario="A user is requesting help finding a local service provider.",
            input_format=("Return only a valid JSON object with exactly these fields: service_type, "
                          "location_city, location_area, urgency, budget, additional_details. urgency must "
                          "be one of IMMEDIATELY, TODAY, THIS_WEEK, NOT_URGENT; budget must be one of "
                          "LOW, MEDIUM, HIGH, NO_BUDGET; additional_details must be a string or null. "
                          "Vary plausible requests while keeping them answerable from the seed context."),
            expected_output_format="A concise expected response grounded only in the seed context; do not add unsupported provider facts.",
        ),
    )
    generated = synthesizer.generate_goldens_from_goldens(
        goldens=seed_goldens,
        max_goldens_per_golden=per_seed,
        include_expected_output=True,
    )
    if len(generated) != args.target_count:
        raise RuntimeError(f"DeepEval produced {len(generated)} goldens, expected {args.target_count}; output not saved")
    dataset = EvaluationDataset(goldens=generated)
    Path(args.out_dir).mkdir(parents=True, exist_ok=True)
    dataset.save_as(file_type="json", directory=args.out_dir, file_name=args.file_name)
    print(f"Saved {len(generated)} synthetic cases to {Path(args.out_dir) / (args.file_name + '.json')}")


if __name__ == "__main__":
    main()
