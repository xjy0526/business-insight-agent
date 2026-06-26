import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  channelContribution,
  contributionBars,
  reportActions,
  reportProblems,
  reportSections,
} from "../data/mockData.js";
import {
  Card,
  DataTable,
  Pill,
  PrimaryButton,
  SecondaryButton,
} from "./ui.jsx";

export default function WeeklyReport() {
  return (
    <div className="space-y-8">
      <section className="flex items-end justify-between">
        <div>
          <p className="text-xs font-extrabold uppercase tracking-[0.18em] text-aiPurple">
            AI generated operating report
          </p>
          <h2 className="mt-3 text-3xl font-extrabold tracking-tight text-ink">
            Weekly operating report
          </h2>
          <p className="mt-2 max-w-3xl text-sm font-medium text-muted">
            Generated for May 8 - May 14 using revenue, product, channel and
            anomaly evidence.
          </p>
        </div>
        <div className="flex gap-3">
          <SecondaryButton>Regenerate</SecondaryButton>
          <PrimaryButton>Export report</PrimaryButton>
        </div>
      </section>

      <section className="grid grid-cols-[0.9fr_1fr] gap-6">
        <Card className="p-6">
          <div className="flex items-start justify-between">
            <h2 className="text-lg font-extrabold text-ink">本周经营概况</h2>
            <Pill tone="purple">Health score 82</Pill>
          </div>
          <p className="mt-8 text-sm font-medium leading-7 text-slate-600">
            本周 GMV 为 $812.6K，环比下降 8.6%。订单量下降 5.2%，转化率下降
            0.8pp，客单价小幅增长 2.1%。整体经营健康分为 82，主要风险集中在搜索流量、核心商品转化和退款评论。
          </p>
        </Card>

        <Card className="bg-gradient-to-br from-blue-50 to-violet-50 p-6">
          <h2 className="text-lg font-extrabold text-indigo-950">预期收益</h2>
          <p className="mt-8 text-sm font-semibold leading-7 text-slate-700">
            若完成关键词恢复、商品详情页优化和高意向优惠券触达，预计 7 天内可追回
            $24K - $36K GMV，转化率提升 0.4 - 0.7pp，退款率回落 0.6pp。
          </p>
          <div className="mt-7 h-14">
            <ResponsiveContainer height="100%" width="100%">
              <BarChart data={contributionBars}>
                <XAxis dataKey="driver" hide />
                <YAxis hide />
                <Tooltip cursor={{ fill: "rgba(37,99,235,.05)" }} />
                <Bar dataKey="contribution" radius={[5, 5, 0, 0]}>
                  {contributionBars.map((_, index) => (
                    <Cell
                      fill={["#2563EB", "#7C3AED", "#06B6D4", "#F97316"][index]}
                      key={index}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </section>

      <section className="grid grid-cols-3 gap-6">
        <Card className="p-6" title="核心问题发现">
          <div className="mt-6 space-y-4">
            {reportProblems.map((problem) => (
              <div className="flex items-center gap-4" key={problem.title}>
                <Pill tone={problem.priority === "P0" ? "red" : "amber"}>
                  {problem.priority}
                </Pill>
                <span className="text-sm font-bold text-slate-700">
                  {problem.title}
                </span>
              </div>
            ))}
          </div>
        </Card>

        <Card className="p-6" title="原因归因">
          <div className="mt-6 grid grid-cols-[128px_1fr] items-center gap-4">
            <ResponsiveContainer height={128} width={128}>
              <PieChart>
                <Pie
                  data={channelContribution}
                  dataKey="value"
                  innerRadius={42}
                  outerRadius={58}
                  paddingAngle={4}
                  stroke="none"
                >
                  {channelContribution.map((entry) => (
                    <Cell fill={entry.color} key={entry.name} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <p className="text-sm font-medium leading-6 text-slate-600">
              GMV 缺口主要来自 Search，其次是核心商品转化。广告 ROI 改善但规模不足，无法对冲自然流量下滑。
            </p>
          </div>
        </Card>

        <Card className="p-6" title="行动建议">
          <div className="mt-6 space-y-3">
            {reportActions.map((action) => (
              <div
                className="rounded-lg border border-line bg-slate-50 px-4 py-3 text-xs font-bold leading-5 text-slate-700"
                key={action}
              >
                {action}
              </div>
            ))}
          </div>
        </Card>
      </section>

      <Card className="p-6" title="Report generation package">
        <div className="mt-5">
          <DataTable
            columns={[
              { key: "section", label: "Report section" },
              { key: "content", label: "AI generated content" },
              { key: "confidence", label: "Confidence" },
              { key: "output", label: "Output" },
            ]}
            rows={reportSections}
          />
        </div>
      </Card>
    </div>
  );
}
