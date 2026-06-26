export function Card({ title, subtitle, action, className = "", children }) {
  return (
    <section
      className={`rounded-lg border border-line bg-white shadow-card ${className}`}
    >
      {(title || subtitle || action) && (
        <div className="flex items-start justify-between gap-4 px-6 pt-6">
          <div>
            {title && <h2 className="text-base font-bold text-ink">{title}</h2>}
            {subtitle && (
              <p className="mt-1 text-xs font-medium text-muted">{subtitle}</p>
            )}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function Pill({ children, tone = "blue", className = "" }) {
  const tones = {
    blue: "bg-blue-50 text-aiBlue",
    purple: "bg-violet-50 text-aiPurple",
    green: "bg-green-100 text-green-700",
    amber: "bg-orange-100 text-orange-700",
    red: "bg-red-100 text-red-700",
    slate: "bg-slate-100 text-slate-600",
  };

  return (
    <span
      className={`inline-flex h-7 items-center rounded-full px-3 text-xs font-bold ${tones[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

export function PrimaryButton({ children, className = "", ...props }) {
  return (
    <button
      className={`inline-flex h-10 items-center justify-center rounded-lg bg-gradient-to-r from-aiBlue to-aiPurple px-4 text-sm font-bold text-white shadow-glow transition hover:brightness-105 ${className}`}
      type="button"
      {...props}
    >
      {children}
    </button>
  );
}

export function SecondaryButton({ children, className = "", ...props }) {
  return (
    <button
      className={`inline-flex h-10 items-center justify-center rounded-lg border border-slate-300 bg-white px-4 text-sm font-bold text-slate-700 transition hover:bg-slate-50 ${className}`}
      type="button"
      {...props}
    >
      {children}
    </button>
  );
}

export function MetricCard({ label, value, delta, tone }) {
  const toneMap = {
    risk: "red",
    warn: "amber",
    up: "green",
  };

  return (
    <Card className="min-h-32 px-5 py-4">
      <p className="text-sm font-semibold text-muted">{label}</p>
      <div className="mt-3 text-3xl font-extrabold tracking-tight text-ink">
        {value}
      </div>
      <Pill className="mt-4" tone={toneMap[tone] || "slate"}>
        {delta}
      </Pill>
    </Card>
  );
}

export function DataTable({ columns, rows }) {
  return (
    <div className="overflow-hidden rounded-lg border border-line">
      <table className="w-full border-collapse text-left text-sm">
        <thead className="bg-slate-50 text-xs font-bold uppercase text-muted">
          <tr>
            {columns.map((column) => (
              <th className="px-4 py-3" key={column.key}>
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line bg-white">
          {rows.map((row, rowIndex) => (
            <tr
              key={
                row.id ||
                `${row.metric || row.section || row.product || row.campaign}-${rowIndex}`
              }
            >
              {columns.map((column) => {
                const value = row[column.key];
                const isDown = typeof value === "string" && value.startsWith("-");
                const isUp = typeof value === "string" && value.startsWith("+");
                return (
                  <td
                    className={`px-4 py-3 font-semibold ${
                      isDown
                        ? "text-red-600"
                        : isUp
                          ? "text-green-700"
                          : "text-slate-700"
                    }`}
                    key={column.key}
                  >
                    {value}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
