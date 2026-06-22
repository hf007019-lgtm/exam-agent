# Exam Agent 与政策知识库集成架构

## 1. 总体架构

```text
用户
  |
  v
小程序 / Web 工作台
  |
  | 业务问题、画像、筛选条件、最近对话
  v
exam_agent
  |-- 招考意图判断
  |-- 岗位筛选、分数匹配、风险分析
  |-- gongkao-selection-coach-skill 分析规则
  |
  | 仅在需要政策依据时调用 HTTP API
  v
rag_builder
  |-- 政策、公告、报考指南知识检索
  |-- 返回 answer、citations、sources
  v
exam_agent 整理为业务回答并返回前端
```

职责边界：

- 小程序或 Web 工作台是用户入口，不直接承担招考业务判断。
- `exam_agent` 是招考业务 Agent，负责意图、岗位、分数、风险和最终表达。
- `rag_builder` 是外部知识库服务，只提供政策依据和引用，不负责岗位筛选或排序。
- `gongkao-selection-coach-skill` 提供分析风格与风险规则，不改变结构化事实。

## 2. 为什么前端不直接调用 rag_builder

用户问的是“我能不能报”“这个限制是什么意思”“岗位是否值得加入备选”。这些问题需要同时使用画像、职位表、历史分数和政策依据。

如果前端直接调用 `rag_builder`，会绕过 `exam_agent` 的业务硬规则，也会把知识检索服务暴露成第二套业务入口。统一由 `exam_agent` 编排可以保证：

1. 推荐数量、年份、省份和分数匹配类型仍由代码控制。
2. RAG 只解释政策，不替代岗位筛选和排序。
3. 知识库不可用时，岗位与分数功能仍可继续运行。
4. 前端只维护一套稳定的业务接口。

## 3. 接口契约

`exam_agent` 调用：

```http
POST http://127.0.0.1:18000/api/v1/search/ask
Content-Type: application/json
```

当前 `rag_builder` 的正式请求体只有：

```json
{
  "question": "基层工作经历是什么意思？"
}
```

响应字段：

```json
{
  "answer": "基于知识库生成的回答",
  "answer_type": "grounded",
  "used_retrieval": true,
  "citations": [],
  "sources": []
}
```

`exam_agent` 会把 `grounded` 归一化为 `knowledge_answer`，并兼容 `unanswerable`、`chitchat`。`RAG_TOP_K` 当前只限制进入 Agent 的引用数量，不会发送给上游，因为上游请求模型暂不接收 `top_k`。

## 4. 调用策略

以下问题优先调用政策知识库：

- 政策、公告、资格审查和报考条件解释。
- 应届生、基层工作经历、服务基层项目人员、户籍和服务年限解释。
- 专业目录、学历学位、资格证书、政治面貌和岗位备注解释。

普通岗位推荐不会强制调用政策知识库。单岗位或推荐结果只有出现需要解释的限制条件时才调用，例如最低服务年限、基层经历、应届身份、户籍、资格证书、公安或人民警察额外要求。

知识库结果只用于解释，不参与岗位排序。

## 5. 配置

在 `exam_agent/.env.example` 中提供：

```env
RAG_ENABLED=true
RAG_BASE_URL=http://127.0.0.1:18000
RAG_ASK_PATH=/api/v1/search/ask
RAG_TIMEOUT_SECONDS=20
RAG_TOP_K=5
```

旧配置 `RAG_BUILDER_BASE_URL` 仍兼容。不要把密钥写入代码、文档或日志。

## 6. 本地联调

先按 `rag_builder` 自身文档启动依赖、FastAPI 和必要的 Worker。FastAPI 示例：

```powershell
cd path\to\rag_builder
uvicorn app.main:app --host 127.0.0.1 --port 18000
```

再启动 `exam_agent`：

```powershell
cd path\to\exam_agent_public
uvicorn app.main:app --host 127.0.0.1 --port 18100
```

验证客户端契约和降级逻辑：

```powershell
python scripts/test_rag_client.py
```

在 `rag_builder` 已启动且知识库有相关资料时，可执行真实联调：

```powershell
python scripts/test_rag_client.py --live
```

## 7. 降级与部署注意事项

- 超时、连接失败、非 JSON 响应或无可靠引用时，`exam_agent` 返回空 `citations/sources`，不暴露内部异常。
- 政策问答无来源时可以给保守的通用解释，但必须明确没有检索到可核验来源。
- `raw` 只保留在客户端内部结果中，不进入普通用户响应。
- 部署时通过环境变量配置服务地址，不把两个仓库合并为 monorepo。
- 生产环境应限制 `rag_builder` 的网络访问范围，并为服务间调用增加鉴权、监控和超时告警。
- 最终结论仍以官方公告、职位表、报考指南和资格审查为准。
