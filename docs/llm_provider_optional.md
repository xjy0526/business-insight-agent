# Optional LLM Provider

## 默认模式

项目默认使用 `LLM_PROVIDER=mock`，课程 demo、pytest、eval、notebook 和 CI 都不依赖外部 API。核心事实来自 SQLite 工具、Product Ad Tool 和本地 RAG，因此没有 API key 时仍能完整运行。

## 可选接入

可选 provider 包括 `mock`、`openai`、`qwen`。接入真实模型时，LLM 仅用于报告 phrasing 和自然语言组织，不覆盖工具数字。

```bash
export LLM_PROVIDER=openai
export LLM_API_KEY="..."
export LLM_MODEL="..."
```

```bash
export LLM_PROVIDER=qwen
export LLM_API_KEY="..."
export LLM_MODEL="qwen-plus"
export LLM_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
```

## 事实边界

- Tool results 是事实来源。
- RAG documents 是可引用知识来源，但会经过安全清洗。
- LLM 输出必须遵守 Pydantic/JSON schema 校验和敏感输出过滤。
- LLM 不得改写 `pcvr`、`price`、`target_roi`、`max_cpc`、`roi_status` 等工具字段。
- 调用失败、缺少 API key 或超时时自动 fallback 到 mock，不影响 deterministic demo。

## 课程评测为何不依赖外部 API

课程验收关注工程闭环：Tool Calling、RAG、Trace、Eval、Ablation、Notebook 输出和文档一致性。外部 LLM 会引入网络、费用、随机性和配额风险，因此默认关闭，保证每次运行可复现。
