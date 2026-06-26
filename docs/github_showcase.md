# GitHub 展示说明

这个仓库适合作为 AI 应用工程项目展示，重点不是“能聊天”，而是把 Agent、RAG、Tool Calling、Trace、Eval、Fallback 串成可运行、可验证、可讲解的闭环。

## 推荐展示顺序

1. 打开 README 的架构图，说明用户问题如何进入条件图。
2. 运行 `python -m app.db.init_db`，强调所有指标来自可复现 SQLite 数据。
3. 调用 `/api/agent/analyze`，展示自然语言问题到结构化诊断报告。
4. 展开 `tool_results`，重点看 `gmv_decomposition`、`review_analysis`、`campaign_participation`。
5. 打开 `/api/traces/{trace_id}` 和 `/api/traces/stats`，说明可观测性。
6. 运行 `python -m evals.run_eval --all-modes --fail-under 0.70`，展示 eval case 和阈值门禁。
7. 运行 `python -m evals.run_eval --all-modes`，说明 RAG、Metrics、Review/Campaign、Reflection 和 mock/fallback 的组件贡献。

## 面试时可以强调的亮点

- 指标数字不由 LLM 生成，而由确定性工具计算。
- RAG 只作为业务证据，不替代指标事实。
- Reflection Evidence Checker 会检查结论是否有证据支撑。
- Prompt Guard 会清洗“忽略规则”“输出系统提示词”等注入式指令。
- 没有 API Key、Redis、FAISS、Chroma、LangGraph 时，系统仍能本地跑通。
- 真实 OpenAI/Qwen Provider 已接入 OpenAI-compatible adapter，但测试不依赖真实 Key。
- Trace 与 Eval 让项目具备可观测、可回测、可门禁的工程闭环。

## 一分钟 Demo 命令

```bash
python -m app.db.init_db
uvicorn app.main:app --reload
```

另开终端：

```bash
curl -X POST http://127.0.0.1:8000/api/agent/analyze \
  -H "Content-Type: application/json" \
  -d '{"query":"商品 P1001 最近 GMV 为什么下降？","use_cache":false}'

curl http://127.0.0.1:8000/api/traces/stats?limit=20
python -m evals.run_eval --all-modes --fail-under 0.70
```
