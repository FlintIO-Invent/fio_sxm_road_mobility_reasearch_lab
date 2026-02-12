from __future__ import annotations


def bpr_time(t0: float, flow: float, capacity: float, alpha: float = 0.15, beta: float = 4.0) -> float:
    """Bureau of Public Roads (BPR) travel time function."""
    if capacity <= 0:
        return float(t0)
    x = max(0.0, flow / capacity)
    return float(t0) * (1.0 + alpha * (x**beta))
