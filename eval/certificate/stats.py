"""Interval helpers for the confidence study (no dependencies)."""

from math import sqrt


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    """The Wilson 95% interval of k successes in n."""
    if n == 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / d
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, mid - half), min(1.0, mid + half)


def cp_lower(k: int, n: int, alpha: float = 0.05) -> float:
    """The one-sided Clopper-Pearson lower bound of k successes in n (bisection on the binomial tail)."""
    if k == 0 or n == 0:
        return 0.0
    from math import comb

    def tail(p: float) -> float:  # P(X >= k | p)
        return sum(comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k, n + 1))

    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if tail(mid) < alpha:
            lo = mid
        else:
            hi = mid
    return lo
