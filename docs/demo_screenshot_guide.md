# Demo 截图指南

用于生成 README 和项目展示材料中的截图。

## 截图步骤

1. 启动后端服务：

```bash
uvicorn app.main:app --reload
```

2. 打开浏览器访问：

```text
http://localhost:8000
```

3. 在输入框中输入：

```text
商品 P1001 最近 GMV 为什么下降？
```

4. 点击分析后，截图时建议同时展示：

- `final_answer`：结构化经营诊断报告。
- `tool_results`：Metrics、Review、Campaign、RAG 等工具结果。
- `retrieved_docs`：RAG 命中的知识证据。
- `trace_id`：用于回查 Trace 的链路 ID。

5. 建议将截图保存为：

```text
docs/assets/demo.png
```

README 当前不会引用不存在的图片，避免 GitHub 首页出现破图。截图生成后可以再将图片引用加入 README。
