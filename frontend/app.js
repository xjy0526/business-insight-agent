const queryInput = document.querySelector("#query-input");
const analyzeButton = document.querySelector("#analyze-button");
const answerEl = document.querySelector("#answer");
const traceIdEl = document.querySelector("#trace-id");
const latencyEl = document.querySelector("#latency");
const statusEl = document.querySelector("#run-status");
const adResultsEl = document.querySelector("#ad-results");
const recommendationResultsEl = document.querySelector("#recommendation-results");
const evidenceAlignmentEl = document.querySelector("#evidence-alignment");
const toolResultsEl = document.querySelector("#tool-results");
const retrievedDocsEl = document.querySelector("#retrieved-docs");
const exampleButtons = document.querySelectorAll(".example-button");
const refreshTraceStatsButton = document.querySelector("#refresh-trace-stats");
const traceStatsStatusEl = document.querySelector("#trace-stats-status");
const statsTotalTracesEl = document.querySelector("#stats-total-traces");
const statsCacheHitRateEl = document.querySelector("#stats-cache-hit-rate");
const statsAvgLatencyEl = document.querySelector("#stats-avg-latency");
const statsP95LatencyEl = document.querySelector("#stats-p95-latency");
const statsErrorRateEl = document.querySelector("#stats-error-rate");
const statsTotalTokensEl = document.querySelector("#stats-total-tokens");
const statsEstimatedCostEl = document.querySelector("#stats-estimated-cost");
const intentDistributionEl = document.querySelector("#intent-distribution");
const providerStatusDistributionEl = document.querySelector("#provider-status-distribution");
const traceAlertsEl = document.querySelector("#trace-alerts");
const slowestNodesEl = document.querySelector("#slowest-nodes");
const runFullEvalButton = document.querySelector("#run-full-eval");
const runAblationEvalButton = document.querySelector("#run-ablation-eval");
const evalStatusEl = document.querySelector("#eval-status");
const evalAvgScoreEl = document.querySelector("#eval-avg-score");
const evalEvidenceHitRateEl = document.querySelector("#eval-evidence-hit-rate");
const evalAvgLatencyEl = document.querySelector("#eval-avg-latency");
const evalP95LatencyEl = document.querySelector("#eval-p95-latency");
const evalGateEl = document.querySelector("#eval-gate");
const evalAblationResultsEl = document.querySelector("#eval-ablation-results");

const INTENT_LABELS = {
  business_diagnosis: "经营诊断",
  refund_analysis: "退款分析",
  traffic_analysis: "流量分析",
  review_analysis: "评论分析",
  product_ad_strategy: "商品广告策略",
  sku_mining: "主推品挖掘",
  sku_recall: "Query-SKU 召回",
  bid_recommendation: "ROI 出价建议",
  poi_vs_product_ad_comparison: "POI/商品广告对比",
  unknown: "意图待确认",
};

const PROVIDER_STATUS_LABELS = {
  mock_template: "本地模板生成",
  fallback_report: "降级报告",
  fallback_empty_content: "空响应降级",
  fallback_error: "异常降级",
  success: "真实模型成功",
  error: "模型调用异常",
  not_called: "未调用模型",
};

const ALERT_TYPE_LABELS = {
  error_rate: "错误率告警",
  p95_latency_ms: "P95 耗时告警",
  latency: "耗时告警",
  provider_error: "模型异常告警",
};

const NODE_LABELS = {
  prompt_guard_node: "提示注入防护",
  intent_router_node: "意图识别",
  planner_node: "任务规划",
  metrics_tool_node: "指标工具",
  product_ad_tool_node: "商品广告工具",
  rag_retriever_node: "RAG 检索",
  recommendation_scorer_node: "推荐归因汇总",
  diagnosis_generator_node: "诊断生成",
  reflection_checker_node: "证据校验",
  final_report_node: "最终报告",
};

const EVAL_MODE_LABELS = {
  full_agent: "完整链路",
  no_rag: "禁用 RAG",
  no_review_campaign: "禁用评论/活动工具",
  no_reflection: "禁用证据校验",
  no_metrics_tool: "禁用指标工具",
  mock_only: "仅 mock/fallback",
};

function displayLabel(value, labels) {
  return labels[value] || value || "-";
}

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
    statusEl.textContent = "分析中";
  }
}

function setDebugPayload(toolResults, retrievedDocs, adResults, recommendationResult, evidenceAlignment) {
  adResultsEl.textContent = JSON.stringify(adResults || {}, null, 2);
  recommendationResultsEl.textContent = JSON.stringify(recommendationResult || {}, null, 2);
  evidenceAlignmentEl.textContent = JSON.stringify(evidenceAlignment || {}, null, 2);
  toolResultsEl.textContent = JSON.stringify(toolResults || {}, null, 2);
  retrievedDocsEl.textContent = JSON.stringify(retrievedDocs || [], null, 2);
}

function formatRate(value) {
  if (typeof value !== "number") {
    return "-";
  }
  return `${(value * 100).toFixed(1)}%`;
}

function renderIntentDistribution(intentDistribution) {
  const entries = Object.entries(intentDistribution || {});
  if (!entries.length) {
    intentDistributionEl.innerHTML = "<li>-</li>";
    return;
  }

  intentDistributionEl.innerHTML = entries
    .map(
      ([intent, count]) =>
        `<li><span>${escapeHtml(displayLabel(intent, INTENT_LABELS))}</span><strong>${count}</strong></li>`,
    )
    .join("");
}

function renderProviderStatus(providerDistribution) {
  const entries = Object.entries(providerDistribution || {});
  if (!entries.length) {
    providerStatusDistributionEl.innerHTML = "<li>-</li>";
    return;
  }

  providerStatusDistributionEl.innerHTML = entries
    .map(
      ([status, count]) =>
        `<li><span>${escapeHtml(displayLabel(status, PROVIDER_STATUS_LABELS))}</span><strong>${count}</strong></li>`,
    )
    .join("");
}

function renderTraceAlerts(alerts) {
  if (!Array.isArray(alerts) || !alerts.length) {
    traceAlertsEl.innerHTML = "<li>-</li>";
    return;
  }

  traceAlertsEl.innerHTML = alerts
    .map(
      (alert) => `
        <li>
          <span>${escapeHtml(displayLabel(alert.type, ALERT_TYPE_LABELS))}</span>
          <strong>${escapeHtml(String(alert.actual ?? "-"))}</strong>
        </li>
      `,
    )
    .join("");
}

function renderSlowestNodes(nodes) {
  if (!Array.isArray(nodes) || !nodes.length) {
    slowestNodesEl.innerHTML = '<tr><td colspan="5">-</td></tr>';
    return;
  }

  slowestNodesEl.innerHTML = nodes
    .slice(0, 8)
    .map(
      (node) => `
        <tr>
          <td>${escapeHtml(displayLabel(node.node, NODE_LABELS))}</td>
          <td>${node.count ?? 0}</td>
          <td>${node.avg_latency_ms ?? 0} ms</td>
          <td>${node.p95_latency_ms ?? 0} ms</td>
          <td>${node.error_count ?? 0}</td>
        </tr>
      `,
    )
    .join("");
}

function setEvalLoading(isLoading) {
  runFullEvalButton.disabled = isLoading;
  runAblationEvalButton.disabled = isLoading;
  evalStatusEl.textContent = isLoading ? "评测运行中" : "评测就绪";
}

function renderEvalSummary(overallMetrics, gate) {
  evalAvgScoreEl.textContent = overallMetrics?.avg_score ?? "-";
  evalEvidenceHitRateEl.textContent = overallMetrics?.evidence_hit_rate ?? "-";
  evalAvgLatencyEl.textContent = `${overallMetrics?.avg_latency_ms ?? "-"} ms`;
  evalP95LatencyEl.textContent = `${overallMetrics?.p95_latency_ms ?? "-"} ms`;
  evalGateEl.textContent = gate?.pass === false ? "未通过" : "通过";
}

function renderAblationResults(rows) {
  if (!Array.isArray(rows) || !rows.length) {
    evalAblationResultsEl.innerHTML = '<tr><td colspan="5">-</td></tr>';
    return;
  }

  evalAblationResultsEl.innerHTML = rows
    .map(
      (row) => `
        <tr>
          <td>${escapeHtml(displayLabel(row.mode || row.ablation, EVAL_MODE_LABELS))}</td>
          <td>${row.avg_score ?? "-"}</td>
          <td>${row.evidence_hit_rate ?? "-"}</td>
          <td>${row.avg_latency_ms ?? "-"} ms</td>
          <td>${row.avg_score_delta_vs_full ?? row.delta_vs_baseline ?? 0}</td>
        </tr>
      `,
    )
    .join("");
}

async function runEval(allModes = false) {
  setEvalLoading(true);

  try {
    const response = await fetch("/api/evals/run", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        mode: "full_agent",
        all_modes: allModes,
        fail_under: null,
      }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || `评测请求失败：${response.status}`);
    }

    renderEvalSummary(payload.overall_metrics, payload.gate);
    renderAblationResults(payload.ablation_results);
    evalStatusEl.textContent = allModes ? "消融评测完成" : "完整评测完成";
  } catch (error) {
    evalStatusEl.textContent = "评测失败";
    evalAblationResultsEl.innerHTML = `<tr><td colspan="5">${escapeHtml(
      error.message || "评测运行失败",
    )}</td></tr>`;
  } finally {
    runFullEvalButton.disabled = false;
    runAblationEvalButton.disabled = false;
  }
}

function renderTraceStats(stats) {
  statsTotalTracesEl.textContent = stats.total_traces ?? stats.trace_count ?? "-";
  statsCacheHitRateEl.textContent = formatRate(stats.cache_hit_rate);
  statsAvgLatencyEl.textContent = `${stats.avg_latency_ms ?? "-"} ms`;
  statsP95LatencyEl.textContent = `${stats.p95_latency_ms ?? "-"} ms`;
  statsErrorRateEl.textContent = formatRate(stats.error_rate);
  statsTotalTokensEl.textContent = stats.token_usage_summary?.total_tokens ?? "-";
  statsEstimatedCostEl.textContent =
    stats.token_usage_summary?.estimated_cost !== undefined
      ? `$${stats.token_usage_summary.estimated_cost}`
      : "-";
  renderIntentDistribution(stats.intent_distribution || stats.intent_counts);
  renderProviderStatus(stats.provider_status_distribution);
  renderTraceAlerts(stats.alerts);
  renderSlowestNodes(stats.slowest_nodes);
}

async function loadTraceStats() {
  traceStatsStatusEl.textContent = "加载中";
  refreshTraceStatsButton.disabled = true;

  try {
    const response = await fetch("/api/traces/stats");
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || `链路追踪统计请求失败：${response.status}`);
    }

    renderTraceStats(payload);
    traceStatsStatusEl.textContent = "已更新";
  } catch (error) {
    traceStatsStatusEl.textContent = "加载失败";
    slowestNodesEl.innerHTML = `<tr><td colspan="5">${escapeHtml(
      error.message || "链路追踪统计加载失败",
    )}</td></tr>`;
  } finally {
    refreshTraceStatsButton.disabled = false;
  }
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
  setDebugPayload({}, [], {}, {}, {});
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
    statusEl.textContent = "已完成";
    answerEl.className = "answer";
    answerEl.innerHTML = renderMarkdownLite(payload.answer || "未返回诊断报告。");
    setDebugPayload(
      payload.tool_results,
      payload.retrieved_docs,
      payload.ad_results,
      payload.recommendation_result,
      payload.evidence_alignment,
    );
    loadTraceStats();
  } catch (error) {
    statusEl.textContent = "请求失败";
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
refreshTraceStatsButton.addEventListener("click", loadTraceStats);
runFullEvalButton.addEventListener("click", () => runEval(false));
runAblationEvalButton.addEventListener("click", () => runEval(true));
queryInput.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
    runAnalysis();
  }
});

loadTraceStats();
