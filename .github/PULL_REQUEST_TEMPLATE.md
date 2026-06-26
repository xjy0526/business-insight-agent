## 变更摘要

- 

## 验证结果

- [ ] `python -m app.db.init_db`
- [ ] `ruff check app evals tests`
- [ ] `mypy app evals`
- [ ] `pytest`
- [ ] `python -m evals.run_eval --strict`

## AI 应用工程检查

- [ ] mock/fallback 模式仍可本地运行
- [ ] 新工具或新节点已写入 Trace
- [ ] 关键结论有 Tool 或 RAG 证据支撑
- [ ] 真实 Provider/API 测试使用 mock/monkeypatch，不依赖真实 Key
- [ ] README/docs/interview_notes 已按需更新
