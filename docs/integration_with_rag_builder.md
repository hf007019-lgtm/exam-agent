# RAG Builder 联动测试文档

本文说明 `exam_agent` 如何联动 `rag_builder`，以及如何验证 `/api/v1/agent/analyze` 返回政策来源 `sources`。

## 1. 启动 rag_builder

先进入你的 `rag_builder` 项目目录，按该项目自己的 README 或启动脚本启动以下服务：

- Docker 服务：例如向量库、消息队列、对象存储等依赖服务。
- FastAPI 服务：提供 RAG Builder 的 HTTP API。
- Celery Worker：负责文档解析、切分、入库等异步任务。

`exam_agent` 默认会请求：

```text
http://127.0.0.1:18000/api/v1/search/ask
```

如果你的 RAG Builder 端口不同，需要在 `exam_agent` 的 `.env` 中修改：

```text
RAG_BUILDER_BASE_URL=http://127.0.0.1:18000
```

## 2. 上传政策测试文件

在 RAG Builder 中上传一份测试文件，例如：

```text
广东事业编报考政策测试资料.txt
```

文件内容可以直接复制下面这段：

```text
广东事业编报考政策测试资料

软件工程属于计算机相关专业方向，具体以官方专业目录为准。

部分事业单位信息技术岗位要求本科及以上学历。

部分岗位可能限制应届毕业生身份。

部分岗位可能存在户籍、基层服务经历或资格证书要求。

岗位报考条件应以当年官方公告和岗位表为准。
```

## 3. 等待文档解析成功

上传后，在 RAG Builder 中查看文档状态。

只有当文档状态变成：

```text
SUCCESS
```

再继续测试 `exam_agent`，否则知识库可能还没有可检索内容。

## 4. 启动 exam_agent

在 Exam Agent 项目根目录中启动：

```bash
uvicorn app.main:app --host 127.0.0.1 --port 18100 --reload
```

接口文档地址：

```text
http://127.0.0.1:18100/docs
```

## 5. 调用分析接口

调用：

```text
POST http://127.0.0.1:18100/api/v1/agent/analyze
```

请求体：

```json
{
  "target": "事业编",
  "region": "广东",
  "education": "本科",
  "major": "软件工程",
  "identity": "应届生",
  "question": "我适合报哪些岗位方向？有什么风险？"
}
```

也可以使用项目内脚本：

```bash
python scripts/test_agent_api.py
```

## 6. 验收结果

RAG Builder 联动正常时，重点观察：

- `sources` 不为空。
- `trace` 中 `policy_tool.search_policy_sources` 的状态为 `success`。
- `trace` 中政策检索步骤显示“检索到 X 条政策来源”。
- `analysis_report` 中出现政策依据说明。

如果没有配置大模型，`llm_used` 可以是 `false`，但 `analysis_report` 仍应返回规则版兜底报告。

## 7. sources 为空时的排查方向

如果 `sources` 为空，通常可以按下面顺序排查：

- RAG Builder 没启动。
- 测试政策文件没上传。
- 文档还没解析成功，状态不是 `SUCCESS`。
- `RAG_BUILDER_BASE_URL` 配错。
- 用户问题和政策资料不相关。
- RAG Builder 的 `/api/v1/search/ask` 正常响应，但返回了空结果。

即使 `sources` 为空，`exam_agent` 也应该继续返回岗位匹配、分数线参考、风险提醒和规则版分析报告。
