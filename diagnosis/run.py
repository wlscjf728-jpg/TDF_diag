#!/usr/bin/env python3
from pathlib import Path

from drsim.reporting import write_reports
from drsim.runner import run_all


def main() -> None:
    output_dir = Path(__file__).resolve().parent / "results"
    rows = run_all()
    write_reports(rows, output_dir)
    print(f"wrote {len(rows)} case rows to {output_dir}")


if __name__ == "__main__":
    main()

