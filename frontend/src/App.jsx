import { useState } from "react";
import AppShell from "./components/AppShell.jsx";
import Dashboard from "./components/Dashboard.jsx";
import AiChat from "./components/AiChat.jsx";
import WeeklyReport from "./components/WeeklyReport.jsx";

const pages = {
  dashboard: <Dashboard />,
  chat: <AiChat />,
  report: <WeeklyReport />,
};

export default function App() {
  const [activePage, setActivePage] = useState("dashboard");

  return (
    <AppShell activePage={activePage} onPageChange={setActivePage}>
      {pages[activePage]}
    </AppShell>
  );
}
