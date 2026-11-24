"""Generate DeepEval goldens from the already captured snapshot JSON files.

This script reads local manifest/JSON snapshots only. It never calls the business API.
Running it does make LLM calls, so invoke it only when ready to incur that cost.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv
from common import load_snapshot_providers


def load_contexts(snapshot_path: Path, group_size: int, limit: int | None) -> tuple[list[list[str]], list[str]]:
    rows = load_snapshot_providers(snapshot_path)
    # Group providers into small contexts so comparison queries can be generated
    # without mixing the entire corpus into every prompt.
    contexts: list[list[str]] = []
    sources: list[str] = []
    buckets: dict[str, list[dict]] = {}
    for row in rows:
        buckets.setdefault(str(row["raw_file"]), []).append(row)
    groups = [(source, bucket[i:i + group_size])
              for source, bucket in buckets.items()
              for i in range(0, len(bucket), group_size)]

    for index, (source, group) in enumerate(groups):
        pruned_fields = ("provider_key", "name", "category", "area", "city", "address", "rating",
                         "review_count", "phone", "open_now", "hours")
        contexts.append([
            "Captured business record (use only these supplied facts): "
            + json.dumps({key: row[key] for key in pruned_fields if key in row}, ensure_ascii=False, default=str)
            for row in group
        ])
        sources.append(f"{source}:provider_group_{index + 1}")
    if limit is not None:
        contexts, sources = contexts[:limit], sources[:limit]
    return contexts, sources


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshots", type=Path, default=Path("eval/data/snapshots"),
                        help="Snapshot root or a single snapshot directory containing manifest.json")
    parser.add_argument("--out-dir", type=Path, default=Path("eval/data"))
    parser.add_argument("--file-name", default="goldens_v1")
    parser.add_argument("--model", default="gpt-4o-mini", help="DeepEval supported model name; configure the matching provider credentials")
    parser.add_argument("--group-size", type=int, default=5, help="Provider records per generation context")
    parser.add_argument("--max-contexts", type=int, default=10, help="Cost cap; each context produces at most one golden")
    parser.add_argument("--max-concurrent", type=int, default=2)
    args = parser.parse_args()

    if args.group_size < 1 or args.max_contexts < 1 or args.max_concurrent < 1:
        parser.error("group-size, max-contexts, and max-concurrent must be positive")
    if not args.snapshots.exists():
        parser.error(f"Snapshot path not found: {args.snapshots}")

    try:
        from deepeval.synthesizer import Synthesizer
        from deepeval.synthesizer.config import StylingConfig
    except ImportError as exc:
        raise SystemExit("DeepEval is not installed. Install it in the project environment with: pip install deepeval") from exc

    contexts, sources = load_contexts(args.snapshots, args.group_size, args.max_contexts)
    print(f"Generating from {len(contexts)} contexts; at most {len(contexts)} goldens. This incurs LLM calls.")
    synthesizer = Synthesizer(
        model=args.model,
        async_mode=True,
        max_concurrent=args.max_concurrent,
        cost_tracking=True,
        styling_config=StylingConfig(
            task="Find and recommend local service businesses using only the supplied captured provider records.",
            scenario="A user asks for local service recommendations based on a fixed evaluation snapshot.",
            input_format=("Return only a valid JSON object with exactly these fields: service_type, "
                          "location_city, location_area, urgency, budget, additional_details. urgency must "
                          "be one of IMMEDIATELY, TODAY, THIS_WEEK, NOT_URGENT; budget must be one of "
                          "LOW, MEDIUM, HIGH, NO_BUDGET; additional_details must be a string or null. "
                          "Use realistic requests consistent with the supplied records."),
            expected_output_format="A concise answer grounded only in the supplied records; do not invent missing details.",
        ),
    )
    synthesizer.generate_goldens_from_contexts(
        contexts=contexts,
        source_files=sources,
        include_expected_output=True,
        max_goldens_per_context=1,
    )
    args.out_dir.mkdir(parents=True, exist_ok=True)
    synthesizer.save_as(file_type="json", directory=str(args.out_dir), file_name=args.file_name)


if __name__ == "__main__":
    main()
