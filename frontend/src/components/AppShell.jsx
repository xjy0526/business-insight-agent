import { Pill } from "./ui.jsx";

const navItems = [
  { key: "dashboard", label: "Dashboard" },
  { key: "chat", label: "AI Chat" },
  { key: "report", label: "Weekly Report" },
];

const pageCopy = {
  dashboard: {
    title: "Dashboard",
    subtitle: "Real-time business overview and anomaly alerts",
  },
  chat: {
    title: "AI Chat Assistant",
    subtitle: "Natural-language analysis with structured results and agent trace",
  },
  report: {
    title: "Weekly Report",
    subtitle: "AI-generated weekly narrative with attribution and actions",
  },
};

export default function AppShell({ activePage, onPageChange, children }) {
  const copy = pageCopy[activePage];

  return (
    <div className="mx-auto flex min-h-screen w-[1440px] bg-canvas text-ink">
      <aside className="flex w-[248px] flex-col bg-navy px-4 py-7 text-white">
        <div className="flex items-center gap-3 px-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-gradient-to-br from-aiBlue to-aiPurple text-sm font-extrabold shadow-glow">
            BI
          </div>
          <div>
            <div className="text-base font-extrabold">Business Insight</div>
            <div className="text-xs font-semibold text-indigo-200">Agent MVP</div>
          </div>
        </div>

        <nav className="mt-14 space-y-3">
          {navItems.map((item) => {
            const active = item.key === activePage;
            return (
              <button
                className={`flex h-11 w-full items-center gap-3 rounded-lg px-4 text-left text-sm font-bold transition ${
                  active
                    ? "bg-blue-700/70 text-white"
                    : "text-slate-400 hover:bg-white/5 hover:text-slate-100"
                }`}
                key={item.key}
                onClick={() => onPageChange(item.key)}
                type="button"
              >
                <span
                  className={`h-5 w-5 rounded-md ${
                    active ? "bg-indigo-200" : "bg-slate-700"
                  }`}
                />
                {item.label}
              </button>
            );
          })}
        </nav>

        <div className="mt-auto rounded-lg border border-slate-800 bg-slate-900 p-5">
          <div className="text-sm font-bold text-white">AI Agent Status</div>
          <p className="mt-3 text-xs font-medium leading-5 text-slate-400">
            6 tools ready: metrics, orders, products, channels, anomaly and
            report.
          </p>
          <Pill className="mt-5" tone="green">
            Live
          </Pill>
        </div>
      </aside>

      <main className="flex-1">
        <header className="flex h-[72px] items-center justify-between border-b border-line bg-white px-8">
          <div>
            <h1 className="text-xl font-extrabold tracking-tight">{copy.title}</h1>
            <p className="mt-1 text-xs font-semibold text-muted">{copy.subtitle}</p>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex h-9 w-64 items-center rounded-lg border border-line bg-slate-50 px-4 text-xs font-semibold text-slate-400">
              Search metrics or products
            </div>
            <Pill>Last 7 days</Pill>
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-aiBlue to-aiPurple text-xs font-extrabold text-white">
                BI
              </div>
              <div>
                <div className="text-xs font-extrabold">Aurora Beauty Store</div>
                <div className="text-[11px] font-semibold text-slate-400">
                  Operator workspace
                </div>
              </div>
            </div>
          </div>
        </header>

        <div className="p-8">{children}</div>
      </main>
    </div>
  );
}
