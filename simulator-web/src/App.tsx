import { lazy, type ReactElement } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { AppShell } from "./components/layout/AppShell";

const DashboardPage = lazy(() => import("./pages/DashboardPage").then((module) => ({ default: module.DashboardPage })));
const DevicesPage = lazy(() => import("./pages/DevicesPage").then((module) => ({ default: module.DevicesPage })));
const SessionRunnerPage = lazy(() => import("./pages/SessionRunnerPage").then((module) => ({ default: module.SessionRunnerPage })));
const FallLabPage = lazy(() => import("./pages/FallLabPage").then((module) => ({ default: module.FallLabPage })));
const SleepLabPage = lazy(() => import("./pages/SleepLabPage").then((module) => ({ default: module.SleepLabPage })));
const DiagnosticsPage = lazy(() => import("./pages/DiagnosticsPage").then((module) => ({ default: module.DiagnosticsPage })));
const VerificationPage = lazy(() => import("./pages/VerificationPage").then((module) => ({ default: module.VerificationPage })));
const SettingsPage = lazy(() => import("./pages/SettingsPage").then((module) => ({ default: module.SettingsPage })));

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
        <Route path="session" element={withBoundary(<SessionRunnerPage />)} />
        <Route path="fall-lab" element={withBoundary(<FallLabPage />)} />
        <Route path="sleep-lab" element={withBoundary(<SleepLabPage />)} />
        <Route path="diagnostics" element={withBoundary(<DiagnosticsPage />)} />
        <Route path="verification" element={withBoundary(<VerificationPage />)} />
        <Route path="settings" element={withBoundary(<SettingsPage />)} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
