"""CI evaluation quality gate.

Runs a bounded golden-set evaluation on the hybrid pipeline and fails (exit 1)
if faithfulness or citation accuracy drops below configured thresholds.

Usage:
    uv run python scripts/eval_gate.py --limit 12 --faithfulness 0.85 --citation 0.80

Requires a running Qdrant index and GROQ_API_KEY.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.eval import run_full


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluation quality gate")
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--faithfulness", type=float, default=0.85)
    parser.add_argument("--citation", type=float, default=0.80)
    args = parser.parse_args(argv)

    report = run_full("hybrid", args.limit, save=True)
    agg = report["aggregates"]
    print(
        json.dumps(
            {
                "questions": report["questions"],
                "faithfulness": agg["faithfulness"],
                "citation_accuracy": agg["citation_accuracy"],
                "relevance": agg["relevance"],
                "correct_refusal_rate": agg["correct_refusal_rate"],
                "failures": len(report["failures"]),
            },
            indent=2,
        )
    )

    failures: list[str] = []
    if agg["faithfulness"] is None or agg["faithfulness"] < args.faithfulness:
        failures.append(f"faithfulness {agg['faithfulness']} < {args.faithfulness}")
    if agg["citation_accuracy"] is None or agg["citation_accuracy"] < args.citation:
        failures.append(f"citation_accuracy {agg['citation_accuracy']} < {args.citation}")

    if failures:
        print(f"EVAL GATE FAILED: {'; '.join(failures)}")
        return 1
    print("EVAL GATE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
