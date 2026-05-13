"""FastAPI routes for business metric tools."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.tools.metrics_tool import compare_periods, get_product_basic_info

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


def _parse_iso_date(value: str, field_name: str) -> date:
    """Parse an ISO date and convert validation failures to HTTP 400."""

    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must use YYYY-MM-DD format.",
        ) from error


def _validate_date_range(start_date: str, end_date: str, label: str) -> None:
    """Validate one date range before running expensive metric queries."""

    parsed_start = _parse_iso_date(start_date, f"{label}_start")
    parsed_end = _parse_iso_date(end_date, f"{label}_end")
    if parsed_start > parsed_end:
        raise HTTPException(
            status_code=400,
            detail=f"{label}_start must be earlier than or equal to {label}_end.",
        )


@router.get("/product/{product_id}/compare")
def compare_product_periods(
    product_id: str,
    current_start: str = Query(..., description="Current period start date, YYYY-MM-DD."),
    current_end: str = Query(..., description="Current period end date, YYYY-MM-DD."),
    baseline_start: str = Query(..., description="Baseline period start date, YYYY-MM-DD."),
    baseline_end: str = Query(..., description="Baseline period end date, YYYY-MM-DD."),
) -> dict:
    """Compare product metrics across current and baseline periods."""

    product = get_product_basic_info(product_id)
    if not product.get("found"):
        raise HTTPException(status_code=404, detail=f"product_id not found: {product_id}")

    _validate_date_range(current_start, current_end, "current")
    _validate_date_range(baseline_start, baseline_end, "baseline")

    return compare_periods(
        product_id=product_id,
        current_start=current_start,
        current_end=current_end,
        baseline_start=baseline_start,
        baseline_end=baseline_end,
    )
