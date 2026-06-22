"""Read CSV and Excel uploads into raw table matrices."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SUPPORTED_FILE_EXTENSIONS = {".csv", ".xlsx", ".xls"}
CSV_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030")


@dataclass(slots=True)
class RawTable:
    sheet_name: str
    rows: list[list[Any]]
    source_name: str


def read_import_file(file_path: Path) -> list[RawTable]:
    """Read a supported spreadsheet-like file into one or more raw tables."""
    suffix = file_path.suffix.lower()
    if suffix not in SUPPORTED_FILE_EXTENSIONS:
        raise ValueError(f"暂不支持的文件类型：{suffix}")
    if suffix == ".csv":
        return _read_csv(file_path)
    return _read_excel(file_path)


def _read_csv(file_path: Path) -> list[RawTable]:
    last_error: UnicodeDecodeError | None = None
    for encoding in CSV_ENCODINGS:
        try:
            with file_path.open("r", encoding=encoding, newline="") as file:
                rows = list(csv.reader(file))
            return [
                RawTable(
                    sheet_name=file_path.stem,
                    rows=_trim_empty_edges(rows),
                    source_name=file_path.name,
                )
            ]
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
    raise ValueError(f"CSV 编码不是 UTF-8/GB18030：{last_error}")


def _read_excel(file_path: Path) -> list[RawTable]:
    try:
        import pandas as pd
    except ImportError as exc:
        raise ValueError("读取 Excel 需要安装 pandas、openpyxl 和 xlrd。") from exc

    try:
        workbook = pd.read_excel(file_path, sheet_name=None, header=None, dtype=object)
    except ImportError as exc:
        raise ValueError("读取 Excel 需要安装 openpyxl（.xlsx）或 xlrd（.xls）。") from exc
    except Exception as exc:
        raise ValueError(f"Excel 文件读取失败：{exc}") from exc

    tables: list[RawTable] = []
    for sheet_name, frame in workbook.items():
        normalized_frame = frame.where(pd.notna(frame), None)
        rows = [list(row) for row in normalized_frame.itertuples(index=False, name=None)]
        rows = _trim_empty_edges(rows)
        if rows:
            tables.append(
                RawTable(
                    sheet_name=str(sheet_name),
                    rows=rows,
                    source_name=file_path.name,
                )
            )
    return tables


def _trim_empty_edges(rows: list[list[Any]]) -> list[list[Any]]:
    cleaned = [list(row) for row in rows]
    while cleaned and not any(_has_value(value) for value in cleaned[-1]):
        cleaned.pop()
    return cleaned


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    try:
        if value != value:
            return False
    except Exception:
        pass
    return str(value).strip() != ""

