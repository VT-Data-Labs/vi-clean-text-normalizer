"""Benchmark script for Stage 4 candidate generation.

Measures throughput, candidate counts, and cache efficiency.

Usage:
    uv run python scripts/bench_stage4_candidates.py
    uv run python scripts/bench_stage4_candidates.py --tokens 5000 --cache
"""

from __future__ import annotations

import argparse
import time

from vn_corrector.stage2_lexicon import load_default_lexicon
from vn_corrector.stage4_candidates import CandidateGenerator, CandidateGeneratorConfig
from vn_corrector.tokenizer import tokenize

# A realistic paragraph with common Vietnamese OCR errors
_SAMPLE_TEXT = """
SỐ MÙÔNG (GẠT NGANG)
Dụng cụ pha chế: 1 muỗng cà phê (5ml)
LÂM NGƯỜI NHANH VÀ KIỂM TRA NHIỆT ĐỘ
RỐT NƯỚC VÀO DỤNG CỤ PHA CHẾ THEO LƯỢNG HƯỚNG DẪN
Nhiệt độ nước: 80-90°C
Thời gian chờ: 3-5 phút
Sản phẩm: CP-2024-OCRVN
Liên hệ: 19001234
Hotline: info@example.com
"""


def bench_candidates(args: argparse.Namespace) -> None:
    lexicon = load_default_lexicon(mode="json")

    config = CandidateGeneratorConfig(
        cache_enabled=args.cache,
        enable_diagnostics=False,
    )
    gen = CandidateGenerator(lexicon, config=config)

    # Build a larger corpus by repeating the sample text
    tokens = tokenize(_SAMPLE_TEXT.strip())
    corpus = tokens * max(1, args.tokens // len(tokens))
    total_tokens = len(corpus)

    print(f"Tokens: {total_tokens}")
    print(f"Cache:  {'enabled' if args.cache else 'disabled'}")
    print(f"Warmup: {args.warmup} runs")
    print()

    # Warmup
    for _ in range(args.warmup):
        gen.generate_document(corpus[:50])

    # Benchmark
    start = time.perf_counter()
    doc = gen.generate_document(corpus)
    elapsed = time.perf_counter() - start

    tokens_per_sec = total_tokens / elapsed if elapsed > 0 else float("inf")
    stats = doc.stats

    # p95 generation time per token is not directly available,
    # but we report aggregates
    print("=== Results ===")
    print(f"Elapsed:           {elapsed:.3f}s")
    print(f"Tokens/sec:        {tokens_per_sec:.0f}")
    print(f"Total candidates:  {stats.total_candidates}")
    print(f"Avg candidates:    {stats.avg_candidates_per_token:.2f}")
    print(f"Max candidates:    {stats.max_candidates_seen}")
    print(f"Cache hits:        {stats.cache_hits}")
    if stats.total_tokens > 0:
        print(f"Protected tokens:  {stats.protected_tokens}")
        print(f"Skipped tokens:    {stats.skipped_tokens}")
        print(f"Generated tokens:  {stats.generated_tokens}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Stage 4 candidate generation")
    parser.add_argument(
        "--tokens",
        type=int,
        default=1000,
        help="Number of tokens to generate candidates for (default: 1000)",
    )
    parser.add_argument(
        "--cache",
        action="store_true",
        default=False,
        help="Enable token cache (default: disabled)",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=2,
        help="Number of warmup iterations (default: 2)",
    )
    args = parser.parse_args()
    bench_candidates(args)


if __name__ == "__main__":
    main()
