from __future__ import annotations

"""Convenience entry-point for the baseline experiment.

This wrapper keeps the CLI stable (scripts/run_baseline.py) while the implementation
lives in `src/sxm_mobility/experiments/run_baseline.py`.
"""

from sxm_mobility.experiments.run_baseline import main


if __name__ == "__main__":
    main()
