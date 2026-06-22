"""Province slug registry for folder-style data imports."""

from __future__ import annotations


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


def normalize_province_slug(slug: str) -> str:
    return str(slug or "").strip().lower().replace(" ", "_")


def get_province_name(slug: str) -> str:
    normalized_slug = normalize_province_slug(slug)
    if normalized_slug not in PROVINCE_NAME_BY_SLUG:
        raise ValueError(
            f"未注册省份：{slug}。请先在 scripts/province_registry.py 中补充映射。"
        )
    return PROVINCE_NAME_BY_SLUG[normalized_slug]


def list_province_slugs() -> list[str]:
    return sorted(PROVINCE_NAME_BY_SLUG)
