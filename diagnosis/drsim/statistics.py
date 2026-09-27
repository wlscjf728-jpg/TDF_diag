from __future__ import annotations
import math

def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)

def median(values: list[float]) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    if n % 2 == 1:
        return sorted_vals[n // 2]
    else:
        return (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2.0

def stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = mean(values)
    variance = sum((x - m) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(variance)

def confidence_interval_95(values: list[float]) -> tuple[float, float]:
    # Returns (lower_bound, upper_bound) of the 95% confidence interval
    if not values:
        return 0.0, 0.0
    m = mean(values)
    if len(values) < 2:
        return m, m
    s = stddev(values)
    margin = 1.96 * s / math.sqrt(len(values))
    return m - margin, m + margin

def jaccard_index(set1: set | frozenset, set2: set | frozenset) -> float:
    union_len = len(set1 | set2)
    if union_len == 0:
        return 1.0
    return len(set1 & set2) / union_len
