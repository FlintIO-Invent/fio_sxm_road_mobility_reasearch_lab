from __future__ import annotations

from pathlib import Path

import pandas as pd


def save_bottlenecks_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)
