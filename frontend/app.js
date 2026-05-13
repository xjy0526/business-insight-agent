const queryInput = document.querySelector("#query-input");
const analyzeButton = document.querySelector("#analyze-button");
const answerEl = document.querySelector("#answer");
const traceIdEl = document.querySelector("#trace-id");
const latencyEl = document.querySelector("#latency");
const statusEl = document.querySelector("#run-status");
const toolResultsEl = document.querySelector("#tool-results");
const retrievedDocsEl = document.querySelector("#retrieved-docs");
const exampleButtons = document.querySelectorAll(".example-button");

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderMarkdownLite(text) {
  const lines = text.split(/\r?\n/);
  const html = [];
  let listOpen = false;

  for (const rawLine of lines) {
    const line = rawLine.trim();

    if (!line) {
      if (listOpen) {
        html.push("</ul>");
        listOpen = false;
      }
      continue;
    }

    if (line.startsWith("## ")) {
      if (listOpen) {
        html.push("</ul>");
        listOpen = false;
      }
      html.push(`<h2>${escapeHtml(line.slice(3))}</h2>`);
      continue;
    }

    if (line.startsWith("- ")) {
      if (!listOpen) {
        html.push("<ul>");
        listOpen = true;
      }
      html.push(`<li>${escapeHtml(line.slice(2))}</li>`);
      continue;
    }

    if (listOpen) {
      html.push("</ul>");
      listOpen = false;
    }
    html.push(`<p>${escapeHtml(line)}</p>`);
  }

  if (listOpen) {
    html.push("</ul>");
  }

  return html.join("");
}

function setLoading(isLoading) {
  analyzeButton.disabled = isLoading;
  analyzeButton.textContent = isLoading ? "分析中..." : "开始分析";
  if (isLoading) {
    statusEl.textContent = "Running";
  }
}

function setDebugPayload(toolResults, retrievedDocs) {
  toolResultsEl.textContent = JSON.stringify(toolResults || {}, null, 2);
  retrievedDocsEl.textContent = JSON.stringify(retrievedDocs || [], null, 2);
}

async function runAnalysis() {
  const query = queryInput.value.trim();
  if (!query) {
    answerEl.className = "answer error-state";
    answerEl.textContent = "请输入一个业务问题。";
    return;
  }

  setLoading(true);
  traceIdEl.textContent = "-";
  latencyEl.textContent = "-";
  setDebugPayload({}, []);
  answerEl.className = "answer empty-state";
  answerEl.textContent = "Agent 正在分析业务数据与知识库...";

  try {
    const response = await fetch("/api/agent/analyze", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ query }),
    });

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || `请求失败：${response.status}`);
    }

    traceIdEl.textContent = payload.trace_id || "-";
    latencyEl.textContent = `${payload.latency_ms ?? "-"} ms`;
    statusEl.textContent = "Complete";
    answerEl.className = "answer";
    answerEl.innerHTML = renderMarkdownLite(payload.answer || "未返回诊断报告。");
    setDebugPayload(payload.tool_results, payload.retrieved_docs);
  } catch (error) {
    statusEl.textContent = "Error";
    answerEl.className = "answer error-state";
    answerEl.textContent = error.message || "请求失败，请检查后端服务。";
  } finally {
    setLoading(false);
  }
}

exampleButtons.forEach((button) => {
  button.addEventListener("click", () => {
    queryInput.value = button.textContent.trim();
    queryInput.focus();
  });
});

analyzeButton.addEventListener("click", runAnalysis);
queryInput.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
    runAnalysis();
  }
});
