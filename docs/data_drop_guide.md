# 原始数据投放和导入说明

## 文件应该放在哪里

职位表、岗位表、计划表放到：

```text
raw_private/省份拼音/2025/jobs/
```

进面分数线、最低进面分文件、面试入围名单放到：

```text
raw_private/省份拼音/2025/scores/
```

例如：

```text
raw_private/guangdong/2025/jobs/
raw_private/guangdong/2025/scores/
raw_private/hebei/2025/jobs/
raw_private/hebei/2025/scores/
```

`app/data/jobs` 和 `app/data/scores` 只保留脚本清洗后的旧种子 CSV，不放原始 Excel，也不直接参与正式查询。

## 全国省份目录

全国 34 个省级行政区的目录已经按年份和类型预留完成。以后只需要把原始 Excel 放到对应省份、年份、类型目录里。

广东职位表放到：

```text
raw_private/guangdong/2025/jobs/
```

河北进面分数线放到：

```text
raw_private/hebei/2025/scores/
```

广西职位表放到：

```text
raw_private/guangxi/2025/jobs/
```

广西各市面试入围名单放到：

```text
raw_private/guangxi/2025/scores/
```

`app/data` 不放原始 Excel，只放清洗后的 CSV。competition 竞争比文件暂时不要放，后面单独处理。`.et` 或 `.wps` 文件需要先用 WPS 另存为 `.xlsx`。

`app/data` 按用途分类：

```text
app/data/reference/  # 地区基础表和别名表
app/data/jobs/       # 旧职位表种子 CSV，迁移后不直接查询
app/data/scores/     # 旧分数线种子 CSV，迁移后不直接查询
app/data/legacy/     # 旧测试 CSV 和示例 CSV，字段不足时跳过
```

## 暂不处理 competition

报名人数、竞争比、报考人数、确认人数这类 competition 文件本轮暂不处理。

如果这类文件放进目录，导入脚本会在报告中标记为跳过，不会生成 competition CSV。

## 支持的文件类型

脚本支持读取 `.xls` 和 `.xlsx`。

如果原始文件是 `.et` 或 `.wps`，不要直接导入。请先用 WPS 另存为 `.xlsx`，再放回对应目录运行导入。

## 如何运行导入命令

导入单个省份职位表：

```bash
python scripts/import_folder_data.py --province guangdong --year 2025 --type jobs
```

导入单个省份分数线：

```bash
python scripts/import_folder_data.py --province hebei --year 2025 --type scores
```

导入单个省份 jobs 和 scores：

```bash
python scripts/import_folder_data.py --province guangxi --year 2025 --type all
```

导入注册表中的全部省份：

```bash
python scripts/import_folder_data.py --all --year 2025
```

## 输出文件在哪里

职位表输出到：

```text
app/data/jobs/jobs_省份拼音_年份.csv
```

例如：

```text
app/data/jobs/jobs_guangdong_2025.csv
```

分数线输出到：

```text
app/data/scores/job_scores_省份拼音_年份.csv
```

例如：

```text
app/data/scores/job_scores_guangdong_2025.csv
```

每次运行后会生成导入报告：

```text
docs/import_report_省份拼音_年份.md
```

报告会记录扫描文件、sheet 导入行数、跳过原因、隐私字段风险、输出路径和成功导入条数。

生成旧种子 CSV 后，运行以下命令写入正式 SQLite 数据源：

```bash
python scripts/migrate_builtin_csv_to_db.py
```

该命令可重复执行，已存在的业务行会按稳定键跳过。业务页面和数据中心读取数据库，不直接读取这些 CSV。
