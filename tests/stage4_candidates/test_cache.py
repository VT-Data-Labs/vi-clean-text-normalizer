"""Tests for TokenCache — LRU in-memory cache for candidate results.

Verifies cache hit/miss, LRU eviction ordering, config fingerprinting,
and stats tracking.
"""

from __future__ import annotations

from vn_corrector.stage4_candidates.cache import TokenCache
from vn_corrector.stage4_candidates.config import CandidateGeneratorConfig
from vn_corrector.stage4_candidates.types import Candidate, CandidateEvidence, CandidateSource


def _dummy_candidate(text: str = "test") -> Candidate:
    return Candidate(
        text=text,
        normalized=text.lower(),
        no_tone_key=text.lower(),
        sources={CandidateSource.ORIGINAL},
        evidence=[
            CandidateEvidence(
                source=CandidateSource.ORIGINAL,
                detail="test",
            )
        ],
        is_original=True,
    )


class TestTokenCache:
    """TokenCache behaviour: hit/miss, LRU eviction, fingerprint."""

    def test_cache_miss_returns_none(self) -> None:
        cache = TokenCache()
        config = CandidateGeneratorConfig()
        result = cache.get("test", "", False, config)
        assert result is None

    def test_cache_hit_returns_candidates(self) -> None:
        cache = TokenCache()
        config = CandidateGeneratorConfig()
        candidates = [_dummy_candidate()]
        cache.put("test", "", False, config, candidates)
        result = cache.get("test", "", False, config)
        assert result is not None
        assert len(result) == 1
        assert result[0].text == "test"

    def test_cache_miss_increments_misses(self) -> None:
        cache = TokenCache()
        config = CandidateGeneratorConfig()
        cache.get("test", "", False, config)
        assert cache.misses == 1
        assert cache.hits == 0

    def test_cache_hit_increments_hits(self) -> None:
        cache = TokenCache()
        config = CandidateGeneratorConfig()
        cache.put("test", "", False, config, [_dummy_candidate()])
        cache.get("test", "", False, config)
        assert cache.hits == 1
        assert cache.misses == 0

    def test_different_key_is_miss(self) -> None:
        cache = TokenCache()
        config = CandidateGeneratorConfig()
        cache.put("hello", "", False, config, [_dummy_candidate("hello")])
        result = cache.get("world", "", False, config)
        assert result is None
        assert cache.hits == 0
        assert cache.misses == 1

    def test_different_protected_flag_is_miss(self) -> None:
        cache = TokenCache()
        config = CandidateGeneratorConfig()
        cache.put("test", "", False, config, [_dummy_candidate()])
        result = cache.get("test", "", True, config)
        assert result is None

    def test_different_config_fingerprint_is_miss(self) -> None:
        cache = TokenCache()
        config1 = CandidateGeneratorConfig(max_candidates_per_token=5)
        config2 = CandidateGeneratorConfig(max_candidates_per_token=10)
        cache.put("test", "", False, config1, [_dummy_candidate()])
        result = cache.get("test", "", False, config2)
        assert result is None

    def test_lru_eviction_removes_oldest(self) -> None:
        """When at capacity, the oldest entry is evicted first."""
        cache = TokenCache(maxsize=3)
        config = CandidateGeneratorConfig()

        # Fill cache
        cache.put("a", "", False, config, [_dummy_candidate("a")])
        cache.put("b", "", False, config, [_dummy_candidate("b")])
        cache.put("c", "", False, config, [_dummy_candidate("c")])

        # Access 'a' to make it most recently used
        cache.get("a", "", False, config)

        # Add 'd' — should evict 'b' (now the LRU entry)
        cache.put("d", "", False, config, [_dummy_candidate("d")])

        assert cache.get("a", "", False, config) is not None
        assert cache.get("b", "", False, config) is None, "b should have been evicted (LRU)"
        assert cache.get("c", "", False, config) is not None
        assert cache.get("d", "", False, config) is not None

    def test_size_property(self) -> None:
        cache = TokenCache()
        config = CandidateGeneratorConfig()
        assert cache.size == 0
        cache.put("a", "", False, config, [_dummy_candidate("a")])
        assert cache.size == 1
        cache.put("b", "", False, config, [_dummy_candidate("b")])
        assert cache.size == 2

    def test_clear_resets_all(self) -> None:
        cache = TokenCache()
        config = CandidateGeneratorConfig()
        cache.put("a", "", False, config, [_dummy_candidate("a")])
        cache.put("b", "", False, config, [_dummy_candidate("b")])
        cache.get("a", "", False, config)
        cache.clear()
        assert cache.size == 0
        assert cache.hits == 0
        assert cache.misses == 0
