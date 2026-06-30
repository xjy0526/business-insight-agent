"""Regression checks for course submission product semantics."""

from __future__ import annotations

import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

ELECTRONICS_TERMS = (
    "无线蓝牙耳机",
    "蓝牙耳机",
    "耳机",
    "蓝牙",
    "续航",
    "音质",
    "降噪",
    "佩戴",
    "佩戴不舒服",
)

COURSE_CORE_FILES = (
    "data/products.csv",
    "data/reviews.csv",
    "data/campaigns.csv",
    "README_COURSE.md",
    "docs/course_report.md",
    "notebooks/course_design_demo.ipynb",
)

LOCAL_SERVICE_NAME_MARKERS = ("水光补水", "补水体验")


def _read_csv_row(path: str, product_id: str) -> dict[str, str]:
    """Return the row for a product id from a repository CSV file."""

    with (PROJECT_ROOT / path).open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            if row.get("product_id") == product_id:
                return row
    raise AssertionError(f"{product_id} not found in {path}")


def test_p1001_is_consistent_local_service() -> None:
    """P1001 should mean the same local-service package across demo datasets."""

    product_row = _read_csv_row("data/products.csv", "P1001")
    ad_candidate_row = _read_csv_row("data/local_ad_sku_candidates.csv", "P1001")

    for row in (product_row, ad_candidate_row):
        product_name = row["product_name"]
        joined_values = " ".join(row.values())
        assert any(marker in product_name for marker in LOCAL_SERVICE_NAME_MARKERS)
        assert not any(term in joined_values for term in ELECTRONICS_TERMS)


def test_no_electronics_terms_in_course_core_files() -> None:
    """Course-facing files should stay in the local-life service scenario."""

    for relative_path in COURSE_CORE_FILES:
        content = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
        assert not any(term in content for term in ELECTRONICS_TERMS), relative_path


def test_notebook_has_no_local_absolute_path() -> None:
    """Committed notebook output should not leak local absolute paths."""

    content = (PROJECT_ROOT / "notebooks/course_design_demo.ipynb").read_text(
        encoding="utf-8"
    )
    blocked_path_fragments = (
        "/Users/",
        "C:\\Users\\",
        "/home/xjy/",
        "Documents/GitHub/ali",
    )

    assert not any(fragment in content for fragment in blocked_path_fragments)
