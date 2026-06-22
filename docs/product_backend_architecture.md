# Exam Agent 产品后端架构

## 1. 整体架构

Exam Agent 现在由四层组成：

1. `app/static`：现有 Web 决策工作台，保留九个一级页面，并增加开发登录、云端会话、云端收藏和运行记录入口。
2. `app/api/v1`：统一业务 API，包含 Agent、认证、用户画像、会话、收藏、报告和运行记录。
3. `app/db`：基于标准库 `sqlite3` 的开发版持久化层，默认数据库为 `data/exam_agent.db`。
4. `app/agents`、`app/tools`、`app/services/rag_client.py`：原有 Agent、岗位/分数工具、Skill Prompt 和外部政策 RAG 客户端。

`exam_agent` 只通过 HTTP 契约调用外部 `rag_builder`，不包含其 PDF、对象存储、任务队列、检索引擎或文档处理实现。

## 2. 用户与认证

- `POST /api/v1/auth/dev-login` 创建或登录开发用户并返回 HS256 JWT。
- `GET /api/v1/auth/me` 返回当前用户与用户画像。
- `AUTH_ENABLED=false` 时，受保护接口可使用默认本地开发用户，方便无登录联调。
- `/api/v1/agent/analyze` 始终保持兼容：有 Token 时关联用户；无 Token 时仍可执行分析。
- 当前 JWT 是开发版基础能力，生产接微信小程序时应新增 `wx-login`，用微信登录凭证换取本系统 Token。

## 3. 用户画像

`GET/PUT /api/v1/user/profile` 保存学历、专业、应届身份、目标地区、考试类型和风险偏好。

Agent 请求的上下文优先级为：

```text
本轮显式筛选条件 > 请求体 profile > 数据库长期画像 > 原接口默认值
```

只有未在本轮明确填写的筛选字段才会读取历史画像，避免画像污染普通咨询。

## 4. 会话与消息

- `POST /api/v1/sessions`
- `GET /api/v1/sessions`
- `GET /api/v1/sessions/{session_id}`
- `DELETE /api/v1/sessions/{session_id}`
- `GET /api/v1/sessions/{session_id}/messages`

用户只能访问自己的会话。`/agent/analyze` 携带 `session_id` 时会读取最近消息并保存本轮用户与助手消息；未携带 `session_id` 且 `save_history=true` 时自动创建会话。

## 5. Agent 运行记录

每次 `/api/v1/agent/analyze` 都生成 `request_id`，并尽力写入：

- `agent_runs`：问题、意图、耗时、RAG 使用状态、引用、来源、trace 和工具列表。
- `tool_calls`：从 trace 拆分出的单步工具名称、输入、输出摘要、状态和错误。

查询接口：

- `GET /api/v1/agent/runs`
- `GET /api/v1/agent/runs/{run_id}`
- `GET /api/v1/agent/runs/{run_id}/tool-calls`

查询结果会过滤密钥、Token、内部文件路径和 debug 字段，并对过长文本截断。数据库写入失败不会阻断 Agent 主回答，响应中的 `persistence_warnings` 会说明降级情况。

## 6. 收藏与报告

收藏接口：

- `POST /api/v1/favorites/jobs`
- `GET /api/v1/favorites/jobs`
- `DELETE /api/v1/favorites/jobs/{favorite_id}`

同一用户重复收藏同一 `job_id` 时执行更新，不重复插入。

报告接口：

- `POST /api/v1/reports`
- `GET /api/v1/reports`
- `GET /api/v1/reports/{report_id}`
- `DELETE /api/v1/reports/{report_id}`

创建报告时可以传 `agent_run_id`，系统会复用该次运行关联的助手回答和政策引用。

## 7. Agent + RAG 调用链路

```text
客户端请求
  -> 可选 JWT 用户识别
  -> 合并长期画像和本轮筛选条件
  -> 读取最近会话消息
  -> 原有 LLM-first Agent 判断意图
  -> 按需调用岗位、分数、风险或政策工具
  -> policy_tool 通过 HTTP 调用 rag_builder
  -> Agent 基于结构化结果生成回答
  -> 保存消息、agent_run、tool_calls、citations
  -> 返回原字段 + session_id/message_id/agent_run_id/request_id
```

RAG 不可用时继续使用原有无来源降级回答，不影响岗位、分数和普通对话能力。

## 8. 小程序接入建议

1. 小程序调用未来的 `wx-login` 换取 Bearer Token。
2. 将 Token 放入 `Authorization: Bearer <token>`。
3. 首次进入读取 `/auth/me` 和 `/user/profile`。
4. 创建或恢复会话后，把 `session_id` 传给 `/agent/analyze`。
5. 收藏、报告和历史页面直接复用现有 JSON API。
6. 普通用户页面只展示友好数据源和政策引用，不展示 trace、内部路径或服务实现细节；运行记录入口应限制为本人或后台角色。

## 9. 本地启动

```powershell
cd path\to\exam_agent_public
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 18100
```

浏览器访问 `http://127.0.0.1:18100/`，接口文档访问 `http://127.0.0.1:18100/docs`。

## 10. 本地测试

```powershell
python -m compileall app
node --check app/static/app.js
python scripts/test_rag_client.py
python scripts/test_auth_and_sessions.py
python scripts/test_agent_persistence.py
```

测试使用独立 SQLite 文件，不依赖外部 RAG 或真实 LLM。`scripts/test_rag_client.py --live` 才会执行外部政策服务联调。
