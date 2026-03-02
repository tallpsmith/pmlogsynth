"""ValueSampler: Gaussian noise, counter accumulation, type coercion."""

import random
from typing import Dict, Optional


class ValueSampler:
    """Applies noise, accumulates counters, and coerces values for PCP output.

    Args:
        noise: Global noise factor (sigma for Gaussian). 0.0 = no noise.
        seed: Optional PRNG seed for deterministic output (Phase 3 --seed support).
    """

    def __init__(self, noise: float = 0.0, seed: Optional[int] = None) -> None:
        self.noise = noise
        self._rng = random.Random(seed)
        self._counters: Dict[str, float] = {}

    def apply_noise(
        self,
        value: float,
        noise_override: Optional[float] = None,
    ) -> float:
        """Apply multiplicative Gaussian noise, clamped to >= 0.

        Args:
            value: The base value.
            noise_override: Override the instance noise factor (per-domain noise).

        Returns:
            Noisy value, always >= 0.0.
        """
        effective_noise = noise_override if noise_override is not None else self.noise
        if effective_noise == 0.0:
            return value
        noisy = value * self._rng.gauss(1.0, effective_noise)
        return max(0.0, noisy)

    def accumulate(self, key: str, delta: float) -> int:
        """Add delta to the running counter for key and return the new total.

        Delta is clamped to >= 0 before addition so counters never decrease.
        """
        safe_delta = max(0.0, delta)
        self._counters[key] = self._counters.get(key, 0.0) + safe_delta
        return int(self._counters[key])

    def coerce_u64(self, value: float) -> int:
        """Clamp value to [0, 2^64 - 1] and return as int."""
        clamped = max(0.0, min(value, 2**64 - 1))
        return int(clamped)
