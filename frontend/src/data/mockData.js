export const kpis = [
  { label: "GMV", value: "$128.4K", delta: "-18.4%", tone: "risk" },
  { label: "Orders", value: "4,862", delta: "-9.7%", tone: "risk" },
  { label: "Conversion", value: "3.84%", delta: "-1.2pp", tone: "warn" },
  { label: "AOV", value: "$26.4", delta: "+2.1%", tone: "up" },
  { label: "Refund Rate", value: "5.6%", delta: "+1.8pp", tone: "warn" },
];

export const gmvTrend = [
  { day: "Mon", actual: 142, forecast: 138 },
  { day: "Tue", actual: 151, forecast: 147 },
  { day: "Wed", actual: 136, forecast: 143 },
  { day: "Thu", actual: 158, forecast: 154 },
  { day: "Fri", actual: 149, forecast: 152 },
  { day: "Sat", actual: 132, forecast: 146 },
  { day: "Sun", actual: 128, forecast: 144 },
];

export const channelContribution = [
  { name: "Search", value: 38, color: "#2563EB" },
  { name: "Ads", value: 27, color: "#7C3AED" },
  { name: "Social", value: 20, color: "#06B6D4" },
  { name: "Direct", value: 15, color: "#F97316" },
];

export const anomalies = [
  {
    metric: "Search traffic",
    impact: "-$18.2K",
    driver: "Keyword rank -21%",
    status: "Open",
  },
  {
    metric: "Sunscreen bundle CVR",
    impact: "-$9.6K",
    driver: "Detail bounce +14%",
    status: "Open",
  },
  {
    metric: "Refund rate",
    impact: "-$3.1K",
    driver: "Size mismatch reviews",
    status: "Watch",
  },
];

export const contributionBars = [
  { driver: "Search traffic", contribution: 52 },
  { driver: "Product CVR", contribution: 27 },
  { driver: "Refund risk", contribution: 9 },
  { driver: "Other", contribution: 12 },
];

export const agentTrace = [
  {
    title: "问题理解",
    body: "识别 GMV 异常诊断意图，时间范围为昨天。",
  },
  {
    title: "指标选择",
    body: "选择 GMV、订单量、转化率、客单价、退款率。",
  },
  {
    title: "数据查询",
    body: "读取昨日数据并对比 7 日基线与上周同期。",
  },
  {
    title: "商品分析",
    body: "定位防晒套装转化率下滑与评价模块变更。",
  },
  {
    title: "渠道归因",
    body: "确认 Search 渠道贡献 52% 的 GMV 缺口。",
  },
  {
    title: "建议生成",
    body: "按收益、执行成本和置信度排序行动建议。",
  },
];

export const recommendations = [
  "Restore 12 high-ROI search keywords",
  "Refresh sunscreen bundle hero proof",
  "Send coupon to high-intent carts",
  "Watch refund comments for size mismatch",
];

export const reportProblems = [
  { priority: "P0", title: "Search traffic down 21%" },
  { priority: "P0", title: "Sunscreen bundle CVR down 14%" },
  { priority: "P1", title: "Refund rate rose to 5.6%" },
  { priority: "P1", title: "Repair serum stock only 2.1 days" },
];

export const reportActions = [
  "Restore high-ROI search keyword budget",
  "Refresh sunscreen bundle hero and reviews",
  "Send coupon to high-intent unpaid carts",
  "Restock repair serum and protect ranking",
];

export const reportSections = [
  {
    section: "Overview",
    content: "Business summary, metric movement, risks",
    confidence: "88%",
    output: "PDF",
  },
  {
    section: "Attribution",
    content: "Channel, product, conversion and refund drivers",
    confidence: "86%",
    output: "Slides",
  },
  {
    section: "Actions",
    content: "Priority, owner, expected benefit",
    confidence: "84%",
    output: "CSV",
  },
];
