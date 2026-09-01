"""Mini timeline aggregation: commit activity buckets for the sparkline."""
from __future__ import annotations

DEFAULT_BUCKETS = 90


def build_timeline(timestamps: list[int], buckets: int = DEFAULT_BUCKETS) -> dict:
    if not timestamps:
        return {"t_min": None, "t_max": None, "points": []}
    t_min = min(timestamps)
    t_max = max(timestamps)
    span = max(1, t_max - t_min)
    counts = [0] * buckets
    for t in timestamps:
        i = int((t - t_min) * buckets / span)
        counts[min(i, buckets - 1)] += 1
    points = [
        {"t": t_min + round((i + 0.5) * span / buckets), "count": c}
        for i, c in enumerate(counts)
    ]
    return {"t_min": t_min, "t_max": t_max, "points": points}
