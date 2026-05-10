"""Real-world OCR markdown integration tests from Chandra output fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from vn_corrector.pipeline import PipelineConfig, TextCorrector


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "ocr"


def _read_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def corrector() -> TextCorrector:
    config = PipelineConfig(
        max_input_chars=20_000,
        fail_closed=False,
        enable_diagnostics=True,
    )
    return TextCorrector(config=config)


def test_chandra_instruction_fixture_contains_real_ocr_errors() -> None:
    text = _read_fixture("chandra_milk_instructions.md")

    expected_errors = [
        "RỘT NƯỚC",
        "SỐ MƯỜNG",
        "ĐẪN KHI",
        "LÂM NGƯỜI NHANH",
        "NHỊỆT ĐỘ",
    ]

    for error in expected_errors:
        assert error in text


@pytest.mark.xfail(reason="Documents current real-world OCR gaps; remove xfail when correction model passes.")
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("RỘT NƯỚC VÀO DỤNG CỤ PHA CHẾ", "RÓT NƯỚC VÀO DỤNG CỤ PHA CHẾ"),
        (
            "CHO SẢN PHẨM THEO SỐ MƯỜNG TƯƠNG ỨNG VỚI LƯỢNG NƯỚC",
            "CHO SẢN PHẨM THEO SỐ MUỖNG TƯƠNG ỨNG VỚI LƯỢNG NƯỚC",
        ),
        ("LẮC NHẺ HOẶC KHUẨY ĐỀU CHO ĐẪN KHI BỘT TAN", "LẮC NHẸ HOẶC KHUẤY ĐỀU CHO ĐẾN KHI BỘT TAN"),
        ("LÂM NGƯỜI NHANH VÀ KIỂM TRA NHỊỆT ĐỘ", "LÀM NGUỘI NHANH VÀ KIỂM TRA NHIỆT ĐỘ"),
        ("PHÚ HỢP THÔNG TƯ 50/2016/TT-BYT", "PHÙ HỢP THÔNG TƯ 50/2016/TT-BYT"),
    ],
)
def test_real_world_ocr_spans_are_corrected(
    corrector: TextCorrector,
    raw: str,
    expected: str,
) -> None:
    result = corrector.correct(raw, domain="milk_instruction")

    assert result.corrected_text == expected


def test_chandra_markdown_preserves_structured_tokens(corrector: TextCorrector) -> None:
    text = _read_fixture("chandra_product_marketing.md")

    result = corrector.correct(text, domain="milk_instruction")

    preserved_tokens = [
        "2'-FL",
        "3-FL",
        "6'-SL",
        "3'-SL",
        "DFL",
        "BB-12<sup>TM</sup>",
        "50/2016/TT-BYT",
        "24/2013/TT-BYT",
        "D80C1Q03",
        "8 934673 002011",
    ]

    for token in preserved_tokens:
        assert token in result.corrected_text


@pytest.mark.xfail(reason="Documents current real-world OCR gap; remove xfail when correction model passes.")
def test_chandra_marketing_fixture_corrects_phu_hop(corrector: TextCorrector) -> None:
    text = _read_fixture("chandra_product_marketing.md")

    result = corrector.correct(text, domain="milk_instruction")

    assert "PHÙ HỢP THÔNG TƯ 50/2016/TT-BYT" in result.corrected_text
    assert "PHÙ HỢP THÔNG TƯ 24/2013/TT-BYT" in result.corrected_text
    assert "PHÚ HỢP" not in result.corrected_text


def test_chandra_instruction_markdown_table_survives_pipeline(corrector: TextCorrector) -> None:
    text = _read_fixture("chandra_milk_instructions.md")

    result = corrector.correct(text, domain="milk_instruction")

    assert '<table border="1">' in result.corrected_text
    assert "<thead>" in result.corrected_text
    assert "</table>" in result.corrected_text
    assert "0 - 1 TUẦN" in result.corrected_text
    assert "60" in result.corrected_text
    assert "7 - 8&lt;/" in result.corrected_text
