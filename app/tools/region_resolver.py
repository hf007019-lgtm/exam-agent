import csv
import re
from functools import lru_cache
from pathlib import Path

from app.db.import_repository import list_imported_dataset_summaries, list_imported_jobs
from app.tools.province_registry import (
    detect_province_in_text,
    get_province_name,
    get_province_slug,
    list_available_job_provinces,
    list_job_cities,
)


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
REFERENCE_DATA_DIR = DATA_DIR / "reference"
CHINA_REGIONS_PATH = REFERENCE_DATA_DIR / "china_regions.csv"
REGION_ALIASES_PATH = REFERENCE_DATA_DIR / "region_aliases.csv"
LEGACY_CHINA_REGIONS_PATH = DATA_DIR / "china_regions.csv"
LEGACY_REGION_ALIASES_PATH = DATA_DIR / "region_aliases.csv"
DEFAULT_PROVINCE = "广西"
UNLIMITED_OPTION = "不限"
DEFAULT_CITY_OPTIONS = ("不限",)
DEFAULT_EDUCATIONS = ("不限", "大专", "本科", "硕士", "博士")
DEFAULT_IDENTITIES = ("不限", "应届生", "服务基层项目人员", "退役大学生士兵", "普通人员")

LEVEL_PRIORITY = {
    "district": 3,
    "city": 2,
    "province": 1,
}


def resolve_region(text: str) -> dict:
    """Resolve province/city/district aliases from free-form text.

    Longest alias wins; ties prefer more specific levels.
    """
    normalized_text = normalize_region_text(text)
    if not normalized_text:
        return _empty_result()

    matches = [
        alias
        for alias in _load_region_aliases()
        if alias["normalized_alias"] and alias["normalized_alias"] in normalized_text
    ]
    if not matches:
        return _empty_result()

    best = max(
        matches,
        key=lambda item: (
            len(item["normalized_alias"]),
            LEVEL_PRIORITY.get(item["level"], 0),
        ),
    )
    return {
        "province": best["province"],
        "city": best["city"],
        "district": best["district"],
        "matched_alias": best["alias"],
        "level": best["level"],
    }


def infer_job_region(job: dict) -> dict:
    """Infer district/city/province from job text fields without mutating CSV data."""
    text = " ".join(
        str(job.get(field, ""))
        for field in [
            "province",
            "region",
            "city",
            "district",
            "department",
            "unit",
            "work_location",
            "location",
            "position_name",
            "position",
            "notes",
        ]
    )
    return resolve_region(text)


def get_region_options(province: str = UNLIMITED_OPTION) -> dict:
    """Return frontend filter options backed by imported job CSV files."""
    selected_province = "" if is_unlimited_region_value(province) else canonical_province(province)
    return {
        "provinces": list_region_provinces(),
        "cities": list_region_cities(selected_province),
        "educations": list(DEFAULT_EDUCATIONS),
        "identities": list(DEFAULT_IDENTITIES),
    }


def list_region_provinces() -> list[str]:
    provinces = [UNLIMITED_OPTION]
    for province in list_available_job_provinces():
        if province and province not in provinces:
            provinces.append(province)
    for dataset in list_imported_dataset_summaries():
        province = str(dataset.get("province") or "").strip()
        if province and province not in provinces:
            provinces.append(province)
    return provinces


def list_region_cities(province: str = UNLIMITED_OPTION) -> list[str]:
    if is_unlimited_region_value(province):
        return list(DEFAULT_CITY_OPTIONS)
    selected_province = canonical_province(province)
    cities = list(DEFAULT_CITY_OPTIONS)
    for city in list_job_cities(selected_province):
        if city and city not in cities:
            cities.append(city)
    for row in list_imported_jobs(province=selected_province, limit=2000):
        city = str(row.get("region") or "").strip()
        if city and city not in cities and city != selected_province:
            cities.append(city)
    return cities


def canonical_province(value: str) -> str:
    text = normalize_region_text(value)
    if not text or is_unlimited_region_value(value):
        return ""

    registry_match = detect_province_in_text(value)
    if registry_match.get("province"):
        return registry_match["province"]

    slug_name = get_province_name(get_province_slug(value))
    if slug_name:
        return slug_name

    for row in _load_china_regions():
        if row["level"] != "province":
            continue
        if text in {normalize_region_text(row["province"]), row["normalized_alias"]}:
            return row["province"]
    return str(value or "").strip()


def is_unlimited_region_value(value: str) -> bool:
    return normalize_region_text(value) in {"", "不限", "全部", "不限制", "全国", "全省"}


def normalize_region_text(text: str) -> str:
    return re.sub(r"[\s,，。；;：:\-_/（）()【】\[\]“”\"'、]+", "", str(text or "").strip())


@lru_cache(maxsize=1)
def _load_region_aliases() -> tuple[dict, ...]:
    aliases = list(_load_china_regions())
    aliases_path = _first_existing_path(REGION_ALIASES_PATH, LEGACY_REGION_ALIASES_PATH)
    if not aliases_path:
        return tuple(aliases)

    with aliases_path.open("r", encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            alias = str(row.get("alias") or "").strip()
            level = str(row.get("level") or "").strip()
            if not alias or level not in LEVEL_PRIORITY:
                continue
            aliases.append(
                {
                    "province": str(row.get("province") or "").strip(),
                    "city": str(row.get("city") or "").strip(),
                    "district": str(row.get("district") or "").strip(),
                    "alias": alias,
                    "normalized_alias": normalize_region_text(alias),
                    "level": level,
                }
            )

    return tuple(aliases)


@lru_cache(maxsize=1)
def _load_china_regions() -> tuple[dict, ...]:
    regions_path = _first_existing_path(CHINA_REGIONS_PATH, LEGACY_CHINA_REGIONS_PATH)
    if not regions_path:
        return tuple()

    aliases = []
    with regions_path.open("r", encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            alias = str(row.get("alias") or "").strip()
            level = str(row.get("level") or "").strip()
            if not alias or level not in {"province", "city"}:
                continue
            aliases.append(
                {
                    "province": str(row.get("province") or "").strip(),
                    "city": str(row.get("city") or "").strip(),
                    "district": "",
                    "alias": alias,
                    "normalized_alias": normalize_region_text(alias),
                    "level": level,
                }
            )

    return tuple(aliases)


def _first_existing_path(*paths: Path) -> Path | None:
    return next((path for path in paths if path.exists()), None)


def _empty_result() -> dict:
    return {
        "province": "",
        "city": "",
        "district": "",
        "matched_alias": "",
        "level": "",
    }
