# Exam Agent

**面向招考数据的 AI 决策分析工作台**

Exam Agent 服务于公务员、省考、国考和事业单位等招考场景。它把结构化岗位数据、历史分数参考、报名缴费数据、政策解释和 AI 对话整合到一个工作台中，帮助用户完成岗位初筛、单岗分析、备选沉淀与风险判断。

项目强调谨慎、透明和可核验：推荐是初筛，不代表录取概率；历史分数是风险参考，不代表当年分数线；缺少报名人数、竞争比或进面分时，会明确说明数据缺口。

## 核心功能

- 招考分析师：支持自由对话、多轮上下文、岗位筛选、分数风险与政策解释。
- 单岗位查询：按职位代码、岗位名称或单位名称定位岗位。
- 岗位备选与对比：沉淀关注岗位，并从备选中选择 2–5 个进行本地比较。
- 分数线参考：谨慎展示已导入的历史进面分及匹配状态。
- 数据中心：在线查看导入数据集、覆盖范围、清洗结果和用户友好统计。
- 我的画像：保存学历、专业、身份、目标地区等长期条件。
- 分析记录：在浏览器本地保存用户可见的选岗决策过程。
- 数据导入：支持 Excel / CSV、多 Sheet 识别、字段映射、清洗预览、人工确认和同一表格多输出。

当前导入类型包括岗位表、进面分数线、候选成绩或资格复审名单、报名/审核/缴费数据和专业目录。Agent 岗位分析卡片可综合展示岗位公开信息、报考限制、历史分数参考、已知报名数据与风险提示。

## 技术栈

- 后端：Python、FastAPI、Pydantic
- 数据处理：pandas、openpyxl、xlrd
- 持久化：SQLite
- AI：OpenAI-compatible API，可在未配置模型时使用规则兜底
- 政策检索：通过独立 HTTP 契约连接外部政策 RAG 服务
- 前端：原生 HTML、CSS、JavaScript

## 项目亮点

- LLM-first 对话入口与确定性岗位工具协作，普通咨询不会无关地触发岗位卡片。
- 推荐数量、年份、省份、分数匹配类型和缺失数据状态由代码硬规则控制。
- 支持多 Sheet 数据识别，以及岗位、报名缴费、分数等共享表头的多输出清洗。
- 导入前提供类型判断、字段映射、异常提示和预览，确认后再写入本地数据库。
- 默认隐藏姓名、准考证号等个人敏感信息；内部路径、数据文件名和 debug 字段不进入普通用户界面。
- 政策检索服务或 LLM 不可用时仍可降级运行，不会编造来源或结构化事实。

## 本地运行

建议使用 Python 3.11 或更高版本。

```powershell
cd path\to\exam_agent_public
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --host 127.0.0.1 --port 18100 --reload
```

启动后可访问：

- 工作台：`http://127.0.0.1:18100/`
- API 文档：`http://127.0.0.1:18100/docs`
- 健康检查：`http://127.0.0.1:18100/api/v1/health`

默认配置使用本地 SQLite，数据库文件会在运行时创建到被 Git 忽略的 `data/`。不配置 LLM 时，核心接口使用规则结果降级；如需 AI 总结，请在本地 `.env` 中填写 `LLM_API_KEY` 和 `LLM_MODEL_NAME`。政策检索服务是可选依赖，可通过 `RAG_ENABLED` 控制。

## 数据导入

工作台和 `POST /api/v1/imports/upload` 支持 `.xlsx`、`.xls`、`.csv`。典型流程为：

1. 上传本地招考文件。
2. 选择或确认 Sheet、数据类型和字段映射。
3. 查看清洗预览、有效行、重复行和风险提示。
4. 对混合表确认需要生成的岗位、报名缴费或分数数据集。
5. 确认后写入本地 SQLite，并在数据中心查看结果。

原始 Excel、导入缓存和数据库都属于本地数据，不应提交到公开仓库。更完整的字段与多输出说明见 [数据导入指南](docs/data_import_guide.md)。

## 数据安全

- `.env`、SQLite、上传文件、真实 Excel/CSV、`data/`、`raw_private/` 默认由 `.gitignore` 排除。
- 公开示例只允许放在 `sample_data/`，且必须是脱敏或完全虚构的数据。
- 姓名、准考证号等字段可用于导入识别和本地核对，但默认不参与 Agent 分析，也不在普通数据视图中展示。
- 提交前仍应执行 Git 跟踪文件、历史对象和敏感字段扫描；`.gitignore` 无法移除已经提交过的数据。

请勿将未经授权的招考原始文件、考生名单或任何个人信息上传到 GitHub。

## 目录结构

```text
exam_agent/
├─ app/
│  ├─ agents/       # 意图、Prompt 与 Agent 编排
│  ├─ api/          # FastAPI 路由
│  ├─ db/           # SQLite 初始化与仓储
│  ├─ imports/      # 文件读取、识别、映射与清洗
│  ├─ schemas/      # 请求与响应模型
│  ├─ services/     # 导入、认证、LLM 与产品服务
│  ├─ static/       # Web 工作台
│  └─ tools/        # 岗位、分数、政策和风险工具
├─ docs/            # 架构、导入、Agent 与验收文档
├─ scripts/         # 导入、迁移和验证脚本
├─ sample_data/     # 仅允许脱敏或虚构示例（可选）
├─ .env.example
├─ .gitignore
└─ requirements.txt
```

## 延伸文档

- [项目概览](docs/project_overview.md)
- [数据导入指南](docs/data_import_guide.md)
- [Agent 分析逻辑](docs/agent_logic.md)
- [最终测试检查清单](docs/final_test_checklist.md)
- [与政策知识库的集成边界](docs/integration_architecture.md)

## 免责声明

本项目仅用于招考信息整理、数据分析和决策辅助。AI 分析、岗位推荐、历史分数与风险提示均不构成报考、录用或资格审查保证。招考政策和岗位条件可能变化，最终请以官方公告、职位表、报考指南、专业目录和资格审查结果为准。
