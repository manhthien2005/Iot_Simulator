import type { ReactElement } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { AppShell } from "./components/layout/AppShell";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DevicesPage } from "./pages/DevicesPage";
import { ScenariosPage } from "./pages/ScenariosPage";
import { SessionRunnerPage } from "./pages/SessionRunnerPage";
import { VerificationPage } from "./pages/VerificationPage";

function NotFoundPage() {
  return (
    <div style={{ padding: "3rem", color: "var(--text-secondary)" }}>
      <h1 className="page-title">Không tìm thấy trang</h1>
      <p className="page-subtitle">Đường dẫn này không tồn tại trong giao diện giả lập.</p>
    </div>
  );
}

function withBoundary(element: ReactElement) {
  return <ErrorBoundary>{element}</ErrorBoundary>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<AppShell />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={withBoundary(<DashboardPage />)} />
        <Route path="devices" element={withBoundary(<DevicesPage />)} />
        <Route path="scenarios" element={withBoundary(<ScenariosPage />)} />
        <Route path="session" element={withBoundary(<SessionRunnerPage />)} />
        <Route path="analytics" element={withBoundary(<AnalyticsPage />)} />
        <Route path="verification" element={withBoundary(<VerificationPage />)} />
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
