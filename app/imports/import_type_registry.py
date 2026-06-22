"""Lightweight registry for structured import type metadata.

The registry centralizes stable type facts without replacing the existing
detector, mapper, cleaner, or repository implementations.
"""

from __future__ import annotations

from typing import Any


COMMON_FIELD_LABELS = {
    "year": "年份",
    "province": "省份",
    "region": "地区",
    "exam_type": "考试类型",
    "job_code": "职位代码",
    "job_name": "岗位名称",
    "unit_name": "招录单位",
    "recruit_count": "招录人数",
    "candidate_no": "准考证号",
    "candidate_name": "姓名",
    "written_score": "笔试成绩",
    "interview_score": "面试成绩",
    "total_score": "总成绩",
    "xingce_score": "行测成绩",
    "shenlun_score": "申论成绩",
    "professional_score": "专业成绩",
    "subject1_name": "科目 1 名称",
    "subject1_score": "科目 1 成绩",
    "subject2_name": "科目 2 名称",
    "subject2_score": "科目 2 成绩",
    "subject3_name": "科目 3 名称",
    "subject3_score": "科目 3 成绩",
    "bonus_score": "加分",
    "review_status": "资格标志",
    "rank": "排名",
    "min_score": "最低进面分",
    "max_score": "最高分",
    "avg_score": "平均分",
    "interview_count": "进面人数",
    "signup_count": "报名人数",
    "approved_count": "审核通过人数",
    "paid_count": "缴费人数",
    "competition_ratio": "竞争比",
    "qualification_requirement": "资格条件",
    "job_description": "职位简介",
    "contact_phone": "咨询电话",
    "work_address": "单位地址",
    "major_requirement_junior_college": "专科专业要求",
    "major_requirement_bachelor": "本科专业要求",
    "major_requirement_graduate": "研究生专业要求",
    "source_file": "来源文件",
    "source_sheet": "来源 Sheet",
}


IMPORT_TYPE_REGISTRY: dict[str, dict[str, Any]] = {
    "job_table": {
        "label": "岗位表",
        "importable": True,
        "target_table": "exam_jobs",
        "catalog_group": "jobs",
        "kind": "jobs",
        "score_like": False,
        "required_fields": ["year", "province", "exam_type", "job_name", "job_code"],
        "optional_fields": [
            "unit_name",
            "major_requirement",
            "major_requirement_junior_college",
            "major_requirement_bachelor",
            "major_requirement_graduate",
            "recruit_count",
            "education_requirement",
            "degree_requirement",
            "qualification_requirement",
            "job_description",
            "contact_phone",
            "work_address",
        ],
        "at_least_one_groups": [],
        "field_labels": COMMON_FIELD_LABELS,
    },
    "score_line_table": {
        "label": "进面分数线表",
        "importable": True,
        "target_table": "exam_score_lines",
        "catalog_group": "scores",
        "kind": "scores",
        "score_like": True,
        "required_fields": ["year", "province", "exam_type", "min_score"],
        "optional_fields": [
            "job_code",
            "unit_name",
            "recruit_count",
            "interview_count",
            "major_category",
        ],
        "at_least_one_groups": [],
        "field_labels": COMMON_FIELD_LABELS,
    },
    "candidate_score_table": {
        "label": "笔试面试成绩汇总表",
        "importable": True,
        "target_table": "exam_candidate_scores",
        "catalog_group": "scores",
        "kind": "candidate_scores",
        "score_like": True,
        "required_fields": ["year", "province", "exam_type"],
        "optional_fields": [
            "candidate_no",
            "candidate_name",
            "job_code",
            "job_name",
            "unit_name",
            "written_score",
            "interview_score",
            "total_score",
            "rank",
        ],
        "at_least_one_groups": [["total_score", "written_score", "interview_score"]],
        "field_labels": COMMON_FIELD_LABELS,
    },
    "review_candidate_list": {
        "label": "资格复审人员名单",
        "importable": True,
        "target_table": "exam_review_candidates",
        "catalog_group": "reviews",
        "kind": "review_candidates",
        "score_like": False,
        "required_fields": ["year", "province", "exam_type"],
        "optional_fields": [
            "job_code",
            "job_name",
            "unit_name",
            "recruit_count",
            "candidate_no",
            "candidate_name",
            "subject1_name",
            "subject1_score",
            "subject2_name",
            "subject2_score",
            "subject3_name",
            "subject3_score",
            "bonus_score",
            "written_score",
            "xingce_score",
            "shenlun_score",
            "professional_score",
            "total_score",
            "rank",
            "review_status",
            "remark",
        ],
        "at_least_one_groups": [
            ["job_code", "job_name"],
            [
                "written_score",
                "total_score",
                "xingce_score",
                "shenlun_score",
                "professional_score",
                "subject1_score",
                "subject2_score",
                "subject3_score",
                "candidate_no",
                "candidate_name",
            ],
        ],
        "field_labels": COMMON_FIELD_LABELS,
    },
    "signup_table": {
        "label": "报名 / 缴费人数表",
        "importable": True,
        "target_table": "exam_signup_stats",
        "catalog_group": "other",
        "kind": "signup",
        "score_like": False,
        "required_fields": ["year", "province", "exam_type", "job_code"],
        "optional_fields": [
            "job_name",
            "unit_name",
            "recruit_count",
            "signup_count",
            "approved_count",
            "paid_count",
            "competition_ratio",
        ],
        "at_least_one_groups": [],
        "field_labels": COMMON_FIELD_LABELS,
    },
    "major_catalog": {
        "label": "专业目录表",
        "importable": True,
        "target_table": "exam_major_catalog",
        "catalog_group": "other",
        "kind": "major_catalog",
        "score_like": False,
        "required_fields": ["year", "province", "major_name"],
        "optional_fields": ["major_code", "major_category", "degree_level"],
        "at_least_one_groups": [],
        "field_labels": COMMON_FIELD_LABELS,
    },
    "unknown": {
        "label": "未识别",
        "importable": False,
        "target_table": "",
        "catalog_group": "other",
        "kind": "unknown",
        "score_like": False,
        "required_fields": [],
        "optional_fields": [],
        "at_least_one_groups": [],
        "field_labels": COMMON_FIELD_LABELS,
    },
}


def get_import_type(type_key: str) -> dict[str, Any]:
    return IMPORT_TYPE_REGISTRY.get(type_key, IMPORT_TYPE_REGISTRY["unknown"])


def get_import_type_label(type_key: str) -> str:
    return str(get_import_type(type_key).get("label") or "未识别")


def is_importable_type(type_key: str) -> bool:
    return bool(get_import_type(type_key).get("importable"))


def list_public_import_types() -> list[dict[str, Any]]:
    return [
        {
            "type_key": type_key,
            "label": str(config.get("label") or type_key),
            "importable": bool(config.get("importable")),
            "target_table": str(config.get("target_table") or ""),
            "catalog_group": str(config.get("catalog_group") or "other"),
        }
        for type_key, config in IMPORT_TYPE_REGISTRY.items()
        if type_key != "unknown"
    ]
