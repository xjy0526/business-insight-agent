import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  agentTrace,
  contributionBars,
  recommendations,
} from "../data/mockData.js";
import { Card, Pill, PrimaryButton } from "./ui.jsx";

export default function AiChat() {
  return (
    <div className="grid h-[840px] grid-cols-[430px_354px_300px] gap-6">
      <Card className="flex min-h-0 flex-col p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-extrabold text-ink">Business analysis chat</h2>
            <p className="mt-1 text-xs font-semibold text-muted">
              Natural-language operating question
            </p>
          </div>
          <Pill tone="green">Connected</Pill>
        </div>

        <div className="mt-8 ml-auto max-w-[332px] rounded-lg border border-indigo-200 bg-indigo-50 p-5">
          <p className="text-[15px] font-bold leading-6 text-indigo-950">
            为什么昨天 GMV 下滑？请定位原因并给出优先行动。
          </p>
        </div>

        <div className="mt-7 max-w-[352px] rounded-lg border border-line bg-slate-50 p-5">
          <p className="text-sm font-extrabold text-ink">AI analysis summary</p>
          <p className="mt-4 text-sm font-medium leading-6 text-slate-600">
            昨日 GMV 下滑 18.4%，主要由搜索渠道流量下降与防晒套装转化率下滑共同导致。系统已完成指标查询、商品分析和渠道归因，建议优先恢复搜索关键词投放，并优化核心商品详情页。
          </p>
        </div>

        <div className="mt-10">
          <p className="text-sm font-extrabold text-muted">Suggested prompts</p>
          <div className="mt-4 flex flex-wrap gap-3">
            {["分析商品贡献", "生成行动清单", "生成周报"].map((prompt) => (
              <Pill key={prompt} tone="purple">
                {prompt}
              </Pill>
            ))}
          </div>
        </div>

        <div className="mt-auto flex items-center gap-3 rounded-lg border border-slate-300 bg-slate-50 p-2">
          <input
            className="h-9 flex-1 bg-transparent px-3 text-sm font-semibold text-slate-500 outline-none"
            defaultValue="继续提问，例如：哪些商品拖累最大？"
          />
          <PrimaryButton className="h-9 px-5">Send</PrimaryButton>
        </div>
      </Card>

      <Card className="min-h-0 p-6">
        <div>
          <h2 className="text-lg font-extrabold text-ink">
            Structured analysis result
          </h2>
          <p className="mt-1 text-xs font-semibold text-muted">
            Evidence-backed attribution and actions
          </p>
        </div>

        <div className="mt-8 rounded-lg border border-indigo-200 bg-gradient-to-br from-blue-50 to-violet-50 p-5">
          <div className="flex items-center justify-between">
            <p className="text-sm font-extrabold text-indigo-950">Root cause</p>
            <Pill tone="purple">86%</Pill>
          </div>
          <p className="mt-4 text-sm font-semibold leading-6 text-slate-700">
            Search traffic accounts for 52% of the gap. Sunscreen bundle
            conversion accounts for 27%. Refund increase contributes 9%.
          </p>
        </div>

        <div className="mt-8">
          <h3 className="text-sm font-extrabold text-ink">Evidence</h3>
          <div className="mt-5 h-[148px]">
            <ResponsiveContainer height="100%" width="100%">
              <BarChart data={contributionBars}>
                <CartesianGrid stroke="#E2E8F0" strokeDasharray="3 3" vertical={false} />
                <XAxis
                  axisLine={false}
                  dataKey="driver"
                  tick={{ fill: "#64748B", fontSize: 10, fontWeight: 700 }}
                  tickLine={false}
                />
                <YAxis
                  axisLine={false}
                  tick={{ fill: "#94A3B8", fontSize: 11, fontWeight: 700 }}
                  tickLine={false}
                  width={28}
                />
                <Tooltip cursor={{ fill: "rgba(37,99,235,.06)" }} />
                <Bar dataKey="contribution" fill="#2563EB" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="mt-8">
          <h3 className="text-sm font-extrabold text-ink">Recommended actions</h3>
          <div className="mt-4 space-y-3">
            {recommendations.map((item) => (
              <div
                className="rounded-lg border border-line bg-slate-50 px-4 py-3 text-xs font-bold text-slate-700"
                key={item}
              >
                {item}
              </div>
            ))}
          </div>
        </div>

        <PrimaryButton className="mt-8 w-full">Create report from analysis</PrimaryButton>
      </Card>

      <Card className="min-h-0 p-6">
        <h2 className="text-lg font-extrabold text-ink">Agent Trace</h2>
        <p className="mt-1 text-xs font-semibold text-muted">
          Transparent tool workflow
        </p>

        <div className="mt-9 space-y-0">
          {agentTrace.map((step, index) => (
            <div className="relative grid grid-cols-[28px_1fr] gap-4" key={step.title}>
              {index < agentTrace.length - 1 && (
                <div className="absolute left-[13px] top-8 h-[64px] w-0.5 bg-slate-300" />
              )}
              <div className="relative z-10 flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-aiBlue to-aiPurple text-[11px] font-extrabold text-white">
                {index + 1}
              </div>
              <div
                className={`mb-7 rounded-lg border p-4 ${
                  index === agentTrace.length - 1
                    ? "border-violet-200 bg-violet-50"
                    : "border-line bg-slate-50"
                }`}
              >
                <p className="text-sm font-extrabold text-ink">{step.title}</p>
                <p className="mt-2 text-[11px] font-semibold leading-5 text-muted">
                  {step.body}
                </p>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
