"""Build compact import reports for API previews."""

from __future__ import annotations

from typing import Any


def build_import_report(
    *,
    sheet_reports: list[dict[str, Any]],
    total_rows: int,
    valid_rows: int,
    warning_rows: int,
    duplicate_rows: int,
    warnings: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "total_rows": total_rows,
        "valid_rows": valid_rows,
        "warning_rows": warning_rows,
        "duplicate_rows": duplicate_rows,
        "sheet_count": len(sheet_reports),
        "processed_sheet_count": sum(1 for sheet in sheet_reports if sheet.get("status") == "processed"),
        "sheets": sheet_reports,
        "warning_count": len(warnings),
    }
