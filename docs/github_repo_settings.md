# GitHub 仓库设置建议

本文件记录建议手动配置的 GitHub 仓库展示信息。本阶段不自动调用 `gh` 修改远程仓库设置。

## Description

```text
E-commerce Business Diagnosis Agent with RAG, Tool Calling, Eval, Trace and Fallback.
```

## Topics

```text
agent
rag
llm
fastapi
tool-calling
ecommerce
observability
evaluation
python
docker
```

## README 展示建议

- 保持 README 顶部 30 秒内能看懂项目价值。
- 优先展示 Agent、RAG、Tool Calling、Trace、Eval、Fallback，而不是普通聊天 Demo。
- Demo 截图生成后放在 `docs/assets/demo.png`。
- 评测结果建议定期用 `python -m evals.run_eval` 刷新。
