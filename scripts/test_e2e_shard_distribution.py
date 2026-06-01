#!/usr/bin/env python3
"""
Test suite for E2E test shard distribution algorithm.

Validates that the 10-shard distribution follows the pattern [1,2,1,2,1,2,1,2,1,2]
and scales correctly with increasing spec counts.
"""

import pytest


import pytest


def calculate_shard_distribution(total_specs: int) -> list[int]:
    """
    Calculate E2E test distribution across 10 shards.

    Pattern: Fill even-position shards first (2,4,6,8,10 = indices 1,3,5,7,9),
    then odd-position shards (1,3,5,7,9 = indices 0,2,4,6,8).

    Args:
        total_specs: Total number of E2E spec files

    Returns:
        List of 10 integers representing specs per shard
    """
    dist = [0] * 10
    remaining = total_specs

    # Phase 1: Fill even-position shards (indices 1,3,5,7,9)
    even_positions = [1, 3, 5, 7, 9]
    for pos in even_positions:
        if remaining > 0:
            dist[pos] = 1
            remaining -= 1

    # Phase 2: Fill odd-position shards (indices 0,2,4,6,8)
    odd_positions = [0, 2, 4, 6, 8]
    for pos in odd_positions:
        if remaining > 0:
            dist[pos] = 1
            remaining -= 1

    # Phase 3: Increment even-positions again (1→2)
    for pos in even_positions:
        if remaining > 0:
            dist[pos] += 1
            remaining -= 1

    # Phase 4: Increment odd-positions (1→2)
    for pos in odd_positions:
        if remaining > 0:
            dist[pos] += 1
            remaining -= 1

    # Continue pattern for higher counts
    while remaining > 0:
        for pos in even_positions:
            if remaining > 0:
                dist[pos] += 1
                remaining -= 1
        for pos in odd_positions:
            if remaining > 0:
                dist[pos] += 1
                remaining -= 1

    return dist


@pytest.mark.parametrize("total_specs", range(0, 101))
def test_all_spec_counts(total_specs):
    """Test distribution for all spec counts from 0 to 100."""
    dist = calculate_shard_distribution(total_specs)

    # Always 10 shards
    assert len(dist) == 10, f"Distribution has {len(dist)} shards, expected 10"

    # Sum must equal total
    assert sum(dist) == total_specs, f"Distribution {dist} doesn't sum to {total_specs}"

    # Balance check: max difference ≤1 (for active shards)
    active_shards = [d for d in dist if d > 0]
    if len(active_shards) > 0:
        max_diff = max(active_shards) - min(active_shards)
        assert max_diff <= 1, f"Distribution {dist} has max_diff={max_diff} > 1"


# Spot-check specific distributions to verify pattern
def test_pattern_examples():
    """Verify specific distribution patterns."""
    assert calculate_shard_distribution(0) == [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    assert calculate_shard_distribution(1) == [0, 1, 0, 0, 0, 0, 0, 0, 0, 0]
    assert calculate_shard_distribution(2) == [0, 1, 0, 1, 0, 0, 0, 0, 0, 0]
    assert calculate_shard_distribution(5) == [0, 1, 0, 1, 0, 1, 0, 1, 0, 1]
    assert calculate_shard_distribution(6) == [1, 1, 0, 1, 0, 1, 0, 1, 0, 1]
    assert calculate_shard_distribution(10) == [1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
    assert calculate_shard_distribution(11) == [1, 2, 1, 1, 1, 1, 1, 1, 1, 1]
    assert calculate_shard_distribution(12) == [1, 2, 1, 2, 1, 1, 1, 1, 1, 1]
    assert calculate_shard_distribution(15) == [1, 2, 1, 2, 1, 2, 1, 2, 1, 2]
    assert calculate_shard_distribution(20) == [2, 2, 2, 2, 2, 2, 2, 2, 2, 2]
    assert calculate_shard_distribution(98) == [10, 10, 10, 10, 10, 10, 9, 10, 9, 10]
    assert calculate_shard_distribution(99) == [10, 10, 10, 10, 10, 10, 10, 10, 9, 10]
    assert calculate_shard_distribution(100) == [10, 10, 10, 10, 10, 10, 10, 10, 10, 10]


def test_distribution_sum_matches_total():
    """Sum of distribution should always equal total specs."""
    for total in [0, 1, 5, 10, 15, 20, 25, 50, 75, 98, 99, 100]:
        dist = calculate_shard_distribution(total)
        assert sum(dist) == total, f"Distribution {dist} doesn't sum to {total}"


def test_distribution_is_balanced():
    """Maximum difference between any two shards should be ≤1."""
    for total in range(0, 101):
        dist = calculate_shard_distribution(total)
        # Filter out empty shards for balance check
        active_shards = [d for d in dist if d > 0]
        if len(active_shards) > 0:
            max_diff = max(active_shards) - min(active_shards)
            assert max_diff <= 1, f"Distribution {dist} has max_diff={max_diff} > 1"


def test_distribution_length():
    """Distribution should always have exactly 10 shards."""
    for total in range(0, 101):
        dist = calculate_shard_distribution(total)
        assert len(dist) == 10, f"Distribution has {len(dist)} shards, expected 10"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
