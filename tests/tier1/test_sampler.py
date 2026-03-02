"""Unit tests for sampler.py — ValueSampler."""

from unittest.mock import patch

import pytest

from pmlogsynth.sampler import ValueSampler


class TestApplyNoise:
    def test_zero_noise_returns_exact_value(self) -> None:
        sampler = ValueSampler(noise=0.0)
        assert sampler.apply_noise(100.0) == pytest.approx(100.0)

    def test_zero_noise_with_override_returns_exact(self) -> None:
        sampler = ValueSampler(noise=0.5)
        assert sampler.apply_noise(100.0, noise_override=0.0) == pytest.approx(100.0)

    def test_nonzero_noise_returns_noisy_value(self) -> None:
        sampler = ValueSampler(noise=0.1, seed=42)
        result = sampler.apply_noise(100.0)
        # With seed=42 and gauss(1.0, 0.1), result should be near 100 but not exactly
        assert result >= 0.0
        # Very unlikely to be exactly 100.0 with noise
        # (but let's just check it's in a reasonable range)
        assert 50.0 < result < 200.0

    def test_noise_clamped_to_zero_when_gaussian_goes_negative(self) -> None:
        sampler = ValueSampler(noise=0.5)
        # Patch _rng.gauss to return a negative multiplier
        with patch.object(sampler._rng, "gauss", return_value=-2.0):
            result = sampler.apply_noise(100.0)
        assert result == pytest.approx(0.0)

    def test_noise_override_takes_precedence(self) -> None:
        sampler = ValueSampler(noise=0.0)
        # noise_override=0.0 means no noise even if instance noise is 0
        result = sampler.apply_noise(50.0, noise_override=0.0)
        assert result == pytest.approx(50.0)

    def test_noise_override_nonzero(self) -> None:
        sampler = ValueSampler(noise=0.0, seed=99)
        # Even though instance noise=0, override=0.2 applies noise
        result = sampler.apply_noise(100.0, noise_override=0.2)
        # Just check it's >= 0 and the gauss applied
        assert result >= 0.0

    def test_zero_value_stays_zero(self) -> None:
        sampler = ValueSampler(noise=0.5, seed=1)
        result = sampler.apply_noise(0.0)
        assert result == pytest.approx(0.0)


class TestAccumulate:
    def test_accumulate_adds_delta(self) -> None:
        sampler = ValueSampler()
        result = sampler.accumulate("key1", 100.0)
        assert result == 100

    def test_accumulate_running_total(self) -> None:
        sampler = ValueSampler()
        sampler.accumulate("key1", 100.0)
        result = sampler.accumulate("key1", 50.0)
        assert result == 150

    def test_accumulate_negative_delta_clamped_to_zero(self) -> None:
        sampler = ValueSampler()
        sampler.accumulate("key1", 100.0)
        # Negative delta should be clamped — counter never decreases
        result = sampler.accumulate("key1", -50.0)
        assert result == 100  # unchanged

    def test_accumulate_zero_delta(self) -> None:
        sampler = ValueSampler()
        sampler.accumulate("key1", 100.0)
        result = sampler.accumulate("key1", 0.0)
        assert result == 100

    def test_accumulate_separate_keys_independent(self) -> None:
        sampler = ValueSampler()
        sampler.accumulate("key1", 100.0)
        sampler.accumulate("key2", 200.0)
        assert sampler.accumulate("key1", 10.0) == 110
        assert sampler.accumulate("key2", 10.0) == 210

    def test_accumulate_returns_int(self) -> None:
        sampler = ValueSampler()
        result = sampler.accumulate("key", 1.5)
        assert isinstance(result, int)

    def test_accumulate_three_times(self) -> None:
        sampler = ValueSampler()
        sampler.accumulate("k", 10.0)
        sampler.accumulate("k", 20.0)
        result = sampler.accumulate("k", 30.0)
        assert result == 60


class TestCoerceU64:
    def test_normal_value(self) -> None:
        sampler = ValueSampler()
        assert sampler.coerce_u64(12345.9) == 12345

    def test_negative_clamped_to_zero(self) -> None:
        sampler = ValueSampler()
        assert sampler.coerce_u64(-100.0) == 0

    def test_very_large_clamped_to_max_u64(self) -> None:
        sampler = ValueSampler()
        max_u64 = 2**64 - 1
        result = sampler.coerce_u64(float(2**65))
        assert result == max_u64

    def test_exactly_zero(self) -> None:
        sampler = ValueSampler()
        assert sampler.coerce_u64(0.0) == 0

    def test_returns_int(self) -> None:
        sampler = ValueSampler()
        result = sampler.coerce_u64(42.7)
        assert isinstance(result, int)


class TestDeterminism:
    def test_same_seed_same_output_sequence(self) -> None:
        s1 = ValueSampler(noise=0.2, seed=1234)
        s2 = ValueSampler(noise=0.2, seed=1234)
        results1 = [s1.apply_noise(100.0) for _ in range(10)]
        results2 = [s2.apply_noise(100.0) for _ in range(10)]
        assert results1 == results2

    def test_different_seeds_different_output(self) -> None:
        s1 = ValueSampler(noise=0.2, seed=1)
        s2 = ValueSampler(noise=0.2, seed=2)
        results1 = [s1.apply_noise(100.0) for _ in range(10)]
        results2 = [s2.apply_noise(100.0) for _ in range(10)]
        assert results1 != results2

    def test_no_seed_is_non_reproducible(self) -> None:
        # Two unseeded samplers should produce different sequences
        # (probabilistically — extremely unlikely to match)
        s1 = ValueSampler(noise=0.1)
        s2 = ValueSampler(noise=0.1)
        results1 = [s1.apply_noise(100.0) for _ in range(20)]
        results2 = [s2.apply_noise(100.0) for _ in range(20)]
        assert results1 != results2
