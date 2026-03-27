#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from src.skill_watch import run_skill_watch


def main() -> int:
    parser = argparse.ArgumentParser(description="Monitor ClawHub skill updates and generate Chinese summaries")
    parser.add_argument("--config", default="config/skill_watch.yaml", help="Path to skill watch YAML config")
    parser.add_argument("--dry-run", action="store_true", help="Run the watcher without sending notifications")
    parser.add_argument("--force-notify", action="store_true", help="Force report generation and send even when no change is detected")
    args = parser.parse_args()

    result = run_skill_watch(args.config, dry_run=args.dry_run, force_notify=args.force_notify)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
