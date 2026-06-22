"""Create raw_private province/year folders for folder-style imports."""

from __future__ import annotations

import argparse
from pathlib import Path

from province_registry import PROVINCE_NAME_BY_SLUG


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_PRIVATE_DIR = PROJECT_ROOT / "raw_private"


def main() -> int:
    args = parse_args()
    result = init_raw_private_dirs(args.year)
    print_report(args.year, result)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="初始化 raw_private 省份目录")
    parser.add_argument(
        "--year",
        type=int,
        default=2025,
        help="要创建的年份目录，默认 2025",
    )
    return parser.parse_args()


def init_raw_private_dirs(year: int) -> dict[str, list[Path]]:
    created: list[Path] = []
    existed: list[Path] = []

    for province_slug in PROVINCE_NAME_BY_SLUG:
        for data_type in ("jobs", "scores"):
            path = RAW_PRIVATE_DIR / province_slug / str(year) / data_type
            if path.exists():
                existed.append(path)
                continue
            path.mkdir(parents=True, exist_ok=True)
            created.append(path)

    return {
        "created": created,
        "existed": existed,
    }


def print_report(year: int, result: dict[str, list[Path]]) -> None:
    created = result["created"]
    existed = result["existed"]

    print("raw_private 目录初始化完成")
    print(f"年份：{year}")
    print(f"总省份数量：{len(PROVINCE_NAME_BY_SLUG)}")
    print("")
    print(f"已创建目录：{len(created)}")
    for path in created:
        print(f"- {relative_path(path)}")
    if not created:
        print("- 无")
    print("")
    print(f"已存在目录：{len(existed)}")
    for path in existed:
        print(f"- {relative_path(path)}")
    if not existed:
        print("- 无")
    print("")
    print("使用说明：")
    print("- 职位表、岗位表、计划表放到 raw_private/{province_slug}/{year}/jobs/")
    print("- 最低进面分、进面分数线、面试入围名单放到 raw_private/{province_slug}/{year}/scores/")
    print("- competition 竞争比文件暂不处理")
    print("- .et 或 .wps 文件请先用 WPS 另存为 .xlsx")


def relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
