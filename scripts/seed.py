"""Seed the sample corpus into the index.

Usage:
    uv run python scripts/seed.py

Idempotent: dedup skips chunks already present. Called automatically on first
boot when GROUNDEDDOCS_SEED_ON_BOOT=true and the index is empty.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.container import AppServices


def main() -> int:
    services = AppServices()
    before = services.store.count()
    reports = services.seed_samples()
    print(json.dumps(reports, indent=2))
    print(
        f"\nindex: {before} -> {services.store.count()} chunks "
        f"({sum(r['inserted'] for r in reports)} inserted, "
        f"{sum(r['skipped'] for r in reports)} dedup-skipped)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
