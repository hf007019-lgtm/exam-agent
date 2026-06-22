<p align="center">
  <img src="docs/assets/logo.svg" width="120" alt="Exam Agent Logo">
</p>

<h1 align="center">Exam Agent</h1>

<p align="center">
  面向招考数据的 AI 决策分析工作台
</p>

<p align="center">
  支持招考 Excel 导入、字段映射、清洗预览、数据中心查看与 AI 岗位分析。
</p>

<p align="center">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white">
  <img alt="SQLite" src="https://img.shields.io/badge/SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white">
  <img alt="AI Agent" src="https://img.shields.io/badge/AI-Agent-607D8B?style=flat-square">
  <img alt="Excel Import" src="https://img.shields.io/badge/Excel-Import-5B8C85?style=flat-square&logo=microsoftexcel&logoColor=white">
  <img alt="Data Cleaning" src="https://img.shields.io/badge/Data-Cleaning-6B7F9E?style=flat-square">
  <a href="LICENSE"><img alt="License Apache-2.0" src="https://img.shields.io/badge/License-Apache--2.0-D6A35D?style=flat-square"></a>
</p>

> Exam Agent 不是给聊天界面套一层招考提示词，而是将可核验的结构化数据工具与 Agent 分析能力组合起来：数据由确定性流程检索、清洗和聚合，LLM 负责理解问题、组织解释与提示风险。

## 项目简介

Exam Agent 是面向公务员、省考、国考及事业单位等招考场景的本地数据分析与辅助决策工作台。它把来源各异、格式复杂的招考表格转为可查询的结构化数据，并结合岗位条件、官方分数线、资格复审样本和报名数据生成岗位卡片与风险提示。

项目强调 **本地优先、来源透明、结论可核验**。AI 输出仅用于缩小信息检索范围，最终报考条件与政策解释始终以官方公告、职位表和招录单位说明为准。

## 为什么做这个项目

真实选岗往往需要反复翻阅职位表、分数线、报名人数、资格复审名单与专业目录。不同地区的 Excel 又常含有多 Sheet、合并表头、字段别名、空行和混合数据集，手工整理耗时且容易错位。

Exam Agent 希望补上“数据准备”与“智能分析”之间的断层：先把数据清洗成可核验的事实，再让 Agent 在事实之上回答问题，而不是让模型凭空生成岗位与分数。

## 核心能力

- **复杂表格导入**：适配真实招考 Excel / CSV 的多 Sheet、表头识别、字段别名和异常行。
- **多数据集拆分**：同一个 Sheet 可拆分为岗位、分数线、报名统计等多个输出数据集。
- **人工确认闭环**：在入库前查看字段映射、清洗预览、异常行与重复记录。
- **结构化 Agent 分析**：解析地区、学历、专业、身份、岗位代码等条件后调用工具检索。
- **多来源联合分析**：支持岗位、官方分数线、报名数据、资格复审名单和候选人成绩样本。
- **可核验的数据中心**：在线分页、搜索并核对清洗结果，避免“导入成功但字段错位”。
- **分数来源分层**：明确区分官方最低进面分与资格复审/候选人成绩样本。
- **规则兜底**：LLM 不可用时，仍可完成部分筛选、匹配与结构化分析。

## 功能总览

| 模块 | 能力 |
| --- | --- |
| 招考分析师 | 自然语言问答、岗位推荐、单岗分析、风险判断 |
| 单岗位查询 | 按岗位代码、岗位名称或单位名称定位岗位 |
| 岗位备选与对比 | 收藏候选岗位并进行多岗位横向比较 |
| 分数参考 | 展示官方进面分、资格复审样本和候选人成绩样本 |
| 数据导入 | Excel / CSV 上传、识别、映射、预览、确认入库 |
| 数据中心 | 按数据集查看、搜索和核对结构化结果 |
| 用户画像 | 保存地区、学历、专业、身份等长期筛选条件 |
| 分析记录 | 保留会话、工具调用与报告记录 |

## 系统架构

```text
┌──────────────────────────────────────────────────────────┐
│                    Web 数据分析工作台                    │
│  招考分析师 · 数据导入 · 数据中心 · 岗位对比 · 用户画像  │
└────────────────────────────┬─────────────────────────────┘
                             ↓
┌──────────────────────────────────────────────────────────┐
│                       FastAPI API                         │
│       Agent · Imports · Sessions · Reports · User         │
└───────────────┬─────────────────────┬────────────────────┘
                ↓                     ↓
┌────────────────────────┐  ┌──────────────────────────────┐
│ Agent 编排与结构化工具  │  │ 数据导入与清洗流水线         │
│ 意图 / 岗位 / 分数 / 风险│  │ Sheet / 映射 / 预览 / 拆分   │
└───────────────┬────────┘  └──────────────┬───────────────┘
                └──────────────┬───────────┘
                               ↓
┌──────────────────────────────────────────────────────────┐
│                   SQLite 本地结构化存储                   │
│       岗位 · 分数线 · 报名统计 · 复审/成绩聚合数据        │
└──────────────────────────────────────────────────────────┘
```

## Agent 分析流程

```text
用户问题
  → 意图识别
  → 解析省份、城市、学历、专业、岗位代码
  → 检索岗位
  → 匹配官方分数线 / 资格复审样本 / 报名数据
  → 生成岗位卡片
  → 输出风险提示和数据来源
```

Agent 优先使用本地结构化工具查询事实；LLM 主要负责解释筛选结果、总结风险与组织表达。数据缺失时会明确说明，不编造分数、竞争比或政策依据。

## 数据导入流程

```text
招考 Excel / CSV
  ↓
Sheet 识别与字段映射
  ↓
清洗预览与人工确认
  ↓
SQLite 本地结构化数据
  ↓
数据中心在线核对
  ↓
Agent 岗位分析
  ↓
岗位卡片 / 分数参考 / 风险提示
```

系统既支持岗位表、分数线表、资格复审名单、报名统计和专业目录等单一数据集，也支持从一个混合 Sheet 产出多个结构化数据集。

## 数据安全设计

- 仓库默认忽略 `.env`、数据库、上传目录、日志以及 Excel / CSV 等本地数据文件。
- 不应向 Git 提交真实招考数据、资格复审明细或任何未经授权的数据。
- 页面和 Agent 结果默认隐藏姓名、准考证号、身份证号、手机号及单条个人成绩明细。
- 原始行数据仅用于本地处理边界，不作为普通页面和 Agent 输出内容。
- 资格复审名单中的成绩只作为样本聚合，不等同于官方最低进面分。
- 公开部署前仍需补充访问控制、文件隔离、日志脱敏、接口限流和数据保留策略。

> 安全边界：本项目提供隐私保护的默认设计，但数据使用者仍需确保数据来源、处理目的和部署方式合法合规。

## 快速开始

要求：Python 3.11+。

```bash
git clone https://github.com/hf007019-lgtm/exam-agent.git
cd exam-agent
python -m venv .venv
```

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --host 127.0.0.1 --port 18100 --reload
```

macOS / Linux：

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --host 127.0.0.1 --port 18100 --reload
```

工作台：`http://127.0.0.1:18100/`

API 文档：`http://127.0.0.1:18100/docs`

## 环境变量

完整示例见 [`.env.example`](.env.example)。常用配置如下：

| 变量 | 用途 | 默认/建议 |
| --- | --- | --- |
| `DATABASE_URL` | SQLite 数据库地址 | `sqlite:///./data/exam_agent.db` |
| `AUTH_ENABLED` | 是否启用本地认证 | 本地开发可设为 `false` |
| `JWT_SECRET_KEY` | JWT 签名密钥 | 部署时必须更换 |
| `LLM_BASE_URL` | OpenAI-compatible API 地址 | 可选 |
| `LLM_API_KEY` | LLM API 密钥 | 不得提交到仓库 |
| `LLM_MODEL_NAME` | 模型名称 | 可选 |
| `RAG_ENABLED` | 是否启用外部政策检索 | `false` |
| `RAG_BASE_URL` | 外部政策服务地址 | 可选 |

未配置 LLM 时，系统仍可通过规则兜底完成部分岗位筛选与结构化分析。

## 项目目录

```text
exam-agent/
├── app/
│   ├── agents/       # Agent 编排、意图识别与 Prompt 构建
│   ├── api/          # FastAPI 路由
│   ├── core/         # 配置与核心设置
│   ├── db/           # SQLite 初始化与数据访问
│   ├── imports/      # 表格识别、字段映射和清洗逻辑
│   ├── schemas/      # 请求与响应模型
│   ├── services/     # 导入、认证、LLM 与产品服务
│   ├── static/       # Web 工作台
│   └── tools/        # 岗位、分数、政策与风险工具
├── docs/             # 架构、导入与 Agent 文档
├── scripts/          # 导入、迁移与辅助脚本
├── .env.example      # 环境变量模板
├── CONTRIBUTING.md   # 贡献指南
├── LICENSE           # Apache License 2.0
└── README.md
```

## 页面与功能展示

当前工作台覆盖以下页面与用户旅程：

| 页面 | 主要操作 |
| --- | --- |
| 概览 | 查看项目能力与数据状态 |
| 招考分析师 | 提问、查看岗位卡片、追问风险 |
| 单岗位查询 | 使用岗位代码或名称精确检索 |
| 岗位备选 / 对比 | 沉淀候选岗位并横向比较 |
| 分数线参考 | 查看不同来源层级的分数信息 |
| 数据导入 | 上传、字段映射、清洗预览、确认入库 |
| 数据中心 | 分页、搜索并在线核对数据 |
| 我的画像 | 管理地区、学历、专业和身份条件 |

> 为避免泄露真实招考数据，仓库不附带真实数据截图。欢迎使用虚构或充分脱敏的数据补充界面示例。

## API 示例

Agent 分析：

```bash
curl -X POST "http://127.0.0.1:18100/api/v1/agent/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "job_recommendation",
    "exam_type": "省考",
    "region": "广西",
    "city": "南宁",
    "education": "本科",
    "major": "计算机类",
    "question": "推荐几个专业条件匹配的岗位，并说明风险"
  }'
```

数据导入（请仅使用合法来源且已脱敏的本地文件）：

```bash
curl -X POST "http://127.0.0.1:18100/api/v1/imports/upload" \
  -F "file=@sanitized-example.xlsx" \
  -F "province=广西" \
  -F "exam_type=省考" \
  -F "year=2026"
```

## 适用场景

- 公务员、事业单位岗位初筛与多岗位对比
- 招考 Excel / CSV 的结构化整理和质量核对
- 历史进面分、报名热度与资格复审样本的联合参考
- 个人学历、专业、身份和地区条件的岗位匹配
- 结构化工具 + Agent 架构的学习、研究与二次开发

不适用于自动代报名、录取结果预测、替代官方资格审查，或处理未经授权的个人敏感数据。

## 项目特点

1. **不是只做聊天**：确定性工具负责数据检索与聚合，Agent 负责理解、编排与解释。
2. **面向真实复杂格式**：支持多 Sheet、表头识别、字段别名、混合数据和人工确认。
3. **多数据源同屏核对**：岗位、分数线、报名数据、资格复审名单可以联合分析。
4. **结果可追溯**：岗位卡片显示数据来源与限制，不把缺失信息包装成确定结论。
5. **隐私默认保护**：姓名、准考证号等个人敏感信息不进入普通展示与 Agent 答案。
6. **分数语义严谨**：样本分与官方最低进面分分层展示，避免误导。
7. **可降级运行**：LLM 不可用时使用规则兜底，核心结构化能力仍可工作。

## Roadmap

- [x] Excel / CSV 导入与清洗预览
- [x] 多 Sheet 识别与多输出数据集
- [x] 数据中心在线核对
- [x] Agent 岗位检索与结构化岗位卡片
- [x] 分数来源分层与敏感字段隐藏
- [ ] 提供完全虚构、可公开的示例数据集
- [ ] 增加脱敏后的页面截图与演示流程
- [ ] 增加 Docker 部署方式
- [ ] 扩展更多地区的字段映射模板
- [ ] 优化 Agent 多轮上下文与解释能力
- [ ] 完善政策 RAG、部署与运维文档

## 文档链接

- [项目概览](docs/project_overview.md)
- [产品与后端架构](docs/product_backend_architecture.md)
- [数据导入指南](docs/data_import_guide.md)
- [Agent 分析逻辑](docs/agent_logic.md)
- [集成架构](docs/integration_architecture.md)
- [政策知识库集成边界](docs/integration_with_rag_builder.md)
- [贡献指南](CONTRIBUTING.md)

## 注意事项

1. 仓库不包含真实招考数据、真实考生信息或本地 SQLite 数据库。
2. 请仅使用来源合法、用途明确并经过必要脱敏的数据文件。
3. `.env`、API Key、数据库、Excel 和 CSV 在提交前必须再次检查。
4. 历史分数与报名热度会随年份和口径变化，不应直接外推当年结果。
5. 公开部署前，请完善认证授权、上传隔离、日志脱敏、速率限制与备份策略。

## 免责声明

本项目仅用于招考信息整理、数据分析与辅助决策。岗位推荐、历史分数参考、报名热度和 AI 风险提示不构成报考建议、录用承诺或资格审查保证。

招考政策、岗位条件、专业目录、报名人数和进面分数可能随时间变化。最终请以官方公告、职位表、报考指南、专业目录及招录单位解释为准。

## License

本项目采用 [Apache License 2.0](LICENSE) 开源许可。

欢迎提交 Issue 与 Pull Request。参与贡献前，请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)，并确保提交内容不含真实招考数据或个人敏感信息。
