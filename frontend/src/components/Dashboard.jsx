import {
  Area,
  AreaChart,
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
  anomalies,
  channelContribution,
  gmvTrend,
  kpis,
} from "../data/mockData.js";
import { Card, DataTable, MetricCard, Pill, PrimaryButton } from "./ui.jsx";

export default function Dashboard() {
  return (
    <div className="space-y-8">
      <section className="flex items-end justify-between">
        <div>
          <p className="text-xs font-extrabold uppercase tracking-[0.18em] text-aiPurple">
            E-commerce operating intelligence
          </p>
          <h2 className="mt-3 text-3xl font-extrabold tracking-tight text-ink">
            Today business snapshot
          </h2>
          <p className="mt-2 max-w-3xl text-sm font-medium text-muted">
            AI monitors revenue, orders, conversion, AOV and refund risk from
            connected commerce data.
          </p>
        </div>
        <Pill tone="purple">Health score 82</Pill>
      </section>

      <section className="grid grid-cols-5 gap-5">
        {kpis.map((metric) => (
          <MetricCard key={metric.label} {...metric} />
        ))}
      </section>

      <section className="grid grid-cols-[2.1fr_1fr] gap-6">
        <Card
          action={
            <div className="flex gap-2">
              <Pill>Actual</Pill>
              <Pill tone="purple">AI forecast</Pill>
            </div>
          }
          className="h-[306px]"
          subtitle="GMV has diverged from the AI forecast since Friday."
          title="GMV trend"
        >
          <div className="h-[230px] px-5 pb-4 pt-4">
            <ResponsiveContainer height="100%" width="100%">
              <AreaChart data={gmvTrend}>
                <defs>
                  <linearGradient id="gmvFill" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="5%" stopColor="#2563EB" stopOpacity={0.24} />
                    <stop offset="95%" stopColor="#2563EB" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#E2E8F0" strokeDasharray="3 3" vertical={false} />
                <XAxis
                  axisLine={false}
                  dataKey="day"
                  tick={{ fill: "#94A3B8", fontSize: 12, fontWeight: 700 }}
                  tickLine={false}
                />
                <YAxis
                  axisLine={false}
                  tick={{ fill: "#94A3B8", fontSize: 12, fontWeight: 700 }}
                  tickLine={false}
                  width={36}
                />
                <Tooltip
                  contentStyle={{
                    border: "1px solid #E2E8F0",
                    borderRadius: 8,
                    boxShadow: "0 12px 28px -16px rgba(15,23,42,.28)",
                  }}
                />
                <Area
                  dataKey="actual"
                  fill="url(#gmvFill)"
                  name="Actual GMV"
                  stroke="#2563EB"
                  strokeWidth={4}
                  type="monotone"
                />
                <Area
                  dataKey="forecast"
                  fill="transparent"
                  name="AI forecast"
                  stroke="#7C3AED"
                  strokeDasharray="8 8"
                  strokeWidth={3}
                  type="monotone"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card
          className="h-[306px]"
          subtitle="Search is still the biggest revenue source and biggest risk."
          title="Channel contribution"
        >
          <div className="grid h-[230px] grid-cols-[150px_1fr] items-center gap-3 px-5 pt-2">
            <ResponsiveContainer height={150} width={150}>
              <PieChart>
                <Pie
                  cx="50%"
                  cy="50%"
                  data={channelContribution}
                  dataKey="value"
                  innerRadius={48}
                  outerRadius={68}
                  paddingAngle={4}
                  stroke="none"
                >
                  {channelContribution.map((entry) => (
                    <Cell fill={entry.color} key={entry.name} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div className="space-y-3">
              {channelContribution.map((channel) => (
                <div className="flex items-center justify-between" key={channel.name}>
                  <span className="flex items-center gap-2 text-xs font-bold text-slate-600">
                    <span
                      className="h-2.5 w-2.5 rounded-full"
                      style={{ background: channel.color }}
                    />
                    {channel.name}
                  </span>
                  <span className="text-xs font-extrabold text-ink">
                    {channel.value}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        </Card>
      </section>

      <section className="grid grid-cols-[0.9fr_1.55fr] gap-6">
        <Card className="bg-gradient-to-br from-blue-50 to-violet-50 p-6">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-extrabold text-indigo-950">
              AI today insight
            </h2>
            <Pill tone="purple">Confidence 86%</Pill>
          </div>
          <p className="mt-6 text-sm font-semibold leading-7 text-slate-700">
            GMV is down mainly because search traffic fell 21% and the sunscreen
            bundle conversion dropped 14%. Ads ROI improved but did not offset
            the organic traffic gap. Recommended first move: recover high-ROI
            search keywords and refresh product proof above the fold.
          </p>
          <PrimaryButton className="mt-7">Ask AI to analyze</PrimaryButton>
        </Card>

        <Card className="p-6" title="Anomaly alerts">
          <div className="mt-5">
            <DataTable
              columns={[
                { key: "metric", label: "Metric" },
                { key: "impact", label: "Impact" },
                { key: "driver", label: "Driver" },
                { key: "status", label: "Status" },
              ]}
              rows={anomalies}
            />
          </div>
        </Card>
      </section>
    </div>
  );
}
