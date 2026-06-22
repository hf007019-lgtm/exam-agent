"""Province name/slug helpers for runtime data lookup."""

from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
JOBS_DATA_DIR = DATA_DIR / "jobs"
SCORES_DATA_DIR = DATA_DIR / "scores"
DEFAULT_DATA_YEAR = 2025

PROVINCE_NAME_BY_SLUG: dict[str, str] = {
    "beijing": "北京",
    "tianjin": "天津",
    "hebei": "河北",
    "shanxi": "山西",
    "neimenggu": "内蒙古",
    "liaoning": "辽宁",
    "jilin": "吉林",
    "heilongjiang": "黑龙江",
    "shanghai": "上海",
    "jiangsu": "江苏",
    "zhejiang": "浙江",
    "anhui": "安徽",
    "fujian": "福建",
    "jiangxi": "江西",
    "shandong": "山东",
    "henan": "河南",
    "hubei": "湖北",
    "hunan": "湖南",
    "guangdong": "广东",
    "guangxi": "广西",
    "hainan": "海南",
    "chongqing": "重庆",
    "sichuan": "四川",
    "guizhou": "贵州",
    "yunnan": "云南",
    "xizang": "西藏",
    "shaanxi": "陕西",
    "gansu": "甘肃",
    "qinghai": "青海",
    "ningxia": "宁夏",
    "xinjiang": "新疆",
    "xianggang": "香港",
    "aomen": "澳门",
    "taiwan": "台湾",
}

PROVINCE_SUFFIX_PATTERN = re.compile(
    r"(省|市|壮族自治区|维吾尔自治区|回族自治区|自治区|特别行政区)$"
)


def normalize_province_slug(slug: str) -> str:
    return str(slug or "").strip().lower().replace(" ", "_")


def normalize_province_text(text: str) -> str:
    value = re.sub(r"[\s,，;；:：。.\-_/（）()【】\[\]“”\"'、]+", "", str(text or "").strip())
    return PROVINCE_SUFFIX_PATTERN.sub("", value)


def get_province_name(slug: str) -> str:
    return PROVINCE_NAME_BY_SLUG.get(normalize_province_slug(slug), "")


def get_province_slug(name: str) -> str:
    normalized_name = normalize_province_text(name)
    if not normalized_name:
        return ""

    direct_slug = normalize_province_slug(name)
    if direct_slug in PROVINCE_NAME_BY_SLUG:
        return direct_slug

    for slug, province_name in PROVINCE_NAME_BY_SLUG.items():
        if normalized_name == normalize_province_text(province_name):
            return slug
    return ""


def detect_province_in_text(text: str) -> dict:
    normalized_text = normalize_province_text(text)
    if not normalized_text:
        return {"province": "", "slug": "", "matched_alias": ""}

    aliases: list[tuple[str, str, str]] = []
    for slug, province_name in PROVINCE_NAME_BY_SLUG.items():
        aliases.extend(
            [
                (province_name, slug, province_name),
                (f"{province_name}省", slug, province_name),
                (f"{province_name}市", slug, province_name),
                (f"{province_name}自治区", slug, province_name),
                (slug, slug, province_name),
            ]
        )
    aliases.extend(
        [
            ("广西壮族自治区", "guangxi", "广西"),
            ("新疆维吾尔自治区", "xinjiang", "新疆"),
            ("西藏自治区", "xizang", "西藏"),
            ("宁夏回族自治区", "ningxia", "宁夏"),
            ("内蒙古自治区", "neimenggu", "内蒙古"),
            ("香港特别行政区", "xianggang", "香港"),
            ("澳门特别行政区", "aomen", "澳门"),
        ]
    )

    for alias, slug, province_name in sorted(
        aliases,
        key=lambda item: len(normalize_province_text(item[0])),
        reverse=True,
    ):
        normalized_alias = normalize_province_text(alias)
        if normalized_alias and normalized_alias in normalized_text:
            return {
                "province": province_name,
                "slug": slug,
                "matched_alias": alias,
            }

    return {"province": "", "slug": "", "matched_alias": ""}


def resolve_requested_province(region: str = "", question: str = "") -> dict:
    """Resolve a target province, with natural-language question taking priority."""
    question_match = detect_province_in_text(question)
    if question_match.get("slug"):
        return {**question_match, "source": "question"}

    if normalize_province_text(region) in {"", "不限", "全部", "不限制", "全国", "全省"}:
        return {"province": "", "slug": "", "matched_alias": "", "source": ""}

    region_match = detect_province_in_text(region)
    if region_match.get("slug"):
        return {**region_match, "source": "filter"}

    return {"province": "", "slug": "", "matched_alias": "", "source": ""}


def jobs_csv_path(province_slug: str, year: int = DEFAULT_DATA_YEAR) -> Path:
    return JOBS_DATA_DIR / f"jobs_{normalize_province_slug(province_slug)}_{year}.csv"


def legacy_jobs_csv_path(province_slug: str, year: int = DEFAULT_DATA_YEAR) -> Path:
    return DATA_DIR / f"jobs_{normalize_province_slug(province_slug)}_{year}.csv"


def scores_csv_path(province_slug: str, year: int = DEFAULT_DATA_YEAR) -> Path:
    return SCORES_DATA_DIR / f"job_scores_{normalize_province_slug(province_slug)}_{year}.csv"


def legacy_scores_csv_path(province_slug: str, year: int = DEFAULT_DATA_YEAR) -> Path:
    return DATA_DIR / f"job_scores_{normalize_province_slug(province_slug)}_{year}.csv"


def has_jobs_csv(province_slug: str, year: int = DEFAULT_DATA_YEAR) -> bool:
    path = jobs_csv_path(province_slug, year)
    return path.exists() and _csv_has_data_rows(path)


def has_scores_csv(province_slug: str, year: int = DEFAULT_DATA_YEAR) -> bool:
    return scores_csv_path(province_slug, year).exists()


def missing_jobs_message(province: str = "") -> str:
    province_text = province or "该省份"
    return (
        f"当前暂未导入{province_text}职位表。"
        "你可以先切换到已导入省份，或导入对应省份职位表后再查询。"
    )


@lru_cache(maxsize=8)
def list_available_job_provinces(year: int = DEFAULT_DATA_YEAR) -> tuple[str, ...]:
    provinces: list[str] = []
    for slug, _path in list_available_job_csvs(year):
        province_name = get_province_name(slug)
        if province_name and province_name not in provinces:
            provinces.append(province_name)
    return tuple(provinces)


@lru_cache(maxsize=8)
def list_available_job_csvs(year: int = DEFAULT_DATA_YEAR) -> tuple[tuple[str, Path], ...]:
    if not JOBS_DATA_DIR.exists():
        return tuple()

    csvs: list[tuple[str, Path]] = []
    pattern = re.compile(rf"^jobs_(?P<slug>[a-z_]+)_{year}\.csv$")
    for path in sorted(JOBS_DATA_DIR.glob(f"jobs_*_{year}.csv")):
        match = pattern.match(path.name)
        if not match or not _csv_has_data_rows(path):
            continue
        slug = normalize_province_slug(match.group("slug"))
        if get_province_name(slug):
            csvs.append((slug, path))
    return tuple(csvs)


def list_job_cities(province: str, year: int = DEFAULT_DATA_YEAR) -> list[str]:
    slug = get_province_slug(province)
    if not slug:
        slug = detect_province_in_text(province).get("slug", "")
    path = jobs_csv_path(slug, year) if slug else Path()
    if not path.exists():
        return []

    cities: list[str] = []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            city = str(row.get("city") or "").strip()
            if city and city not in cities:
                cities.append(city)
    return cities


def _csv_has_data_rows(path: Path) -> bool:
    if not path.exists():
        return False

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return any(True for _ in reader)
