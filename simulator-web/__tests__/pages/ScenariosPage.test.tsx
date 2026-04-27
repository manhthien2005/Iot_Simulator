import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ScenarioOption } from "../../src/types/scenario";

// ---------------------------------------------------------------------------
// Module B smoke — `<ScenariosPage/>`.
//
// Mocks the scenarios + devices service layer so the page renders
// synchronously, then asserts:
//   * Cards render for each scenario.
//   * Category filter narrows the list.
//   * Clicking "Chạy ngay" navigates to /session?scenario=...&device=...
//
// We don't test the BE wire format here — `fetchScenarios` is unit-
// tested at the service level (future work).  The smoke is purely:
// "the FE plumbing wires render → click → navigate".
// ---------------------------------------------------------------------------

const FAKE_SCENARIOS: ScenarioOption[] = [
  {
    id: "fall-hard",
    name: "Té ngã nặng",
    category: "fall",
    description: "Người dùng té đập đầu xuống sàn cứng.",
    expectedOutcome: "BE tự kích hoạt SOS countdown.",
    severity: "critical",
    keySignals: [
      { label: "Acc peak", direction: "up", target: "25 g", severity: "critical" },
    ],
    followUp: [{ kind: "fall_event", detail: "Confirmed fall trong 2s." }],
  },
  {
    id: "vitals-tachy",
    name: "Tăng nhịp tim",
    category: "vitals",
    description: "HR tăng dần do căng thẳng.",
    expectedOutcome: "Stress score lên warning.",
    severity: "warning",
    keySignals: [
      { label: "HR", direction: "up", target: "120 bpm", severity: "warning" },
    ],
    followUp: [],
  },
];

const FAKE_DEVICES = [
  {
    id: "dev-1",
    name: "Watch Alice",
    serialNumber: "SN-001",
    currentScenarioId: "fall-hard",
  },
  {
    id: "dev-2",
    name: "Watch Bob",
    serialNumber: "SN-002",
    currentScenarioId: null,
  },
];

vi.mock("../../src/services/scenarioApi", () => ({
  fetchScenarios: vi.fn(() => Promise.resolve(FAKE_SCENARIOS)),
}));

vi.mock("../../src/hooks/useDevices", () => ({
  useDevices: () => ({ data: FAKE_DEVICES }),
  // The page also imports `useDbDevices` from the same module via
  // other consumers — keep the surface area complete.
  useDbDevices: () => ({ data: [], isLoading: false, error: null, refetch: vi.fn() }),
}));

// react-router's `useNavigate` returns a function; mock so we can
// observe the URL the page tries to push.
const navigateSpy = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>(
    "react-router-dom",
  );
  return {
    ...actual,
    useNavigate: () => navigateSpy,
  };
});

// Import AFTER mocks so the SUT picks up the mocked modules.
import { ScenariosPage } from "../../src/pages/ScenariosPage";

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/scenarios"]}>
        <Routes>
          <Route path="/scenarios" element={<ScenariosPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ScenariosPage smoke", () => {
  beforeEach(() => {
    navigateSpy.mockReset();
  });

  it("renders one card per scenario", async () => {
    renderPage();

    expect(await screen.findByText("Té ngã nặng")).toBeInTheDocument();
    expect(screen.getByText("Tăng nhịp tim")).toBeInTheDocument();
  });

  it("filters scenarios by category tab", async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Té ngã nặng");
    await screen.findByText("Tăng nhịp tim");

    // Switch to "Té ngã" tab — vitals scenarios should disappear.
    await user.click(
      screen.getByRole("button", { name: /Lọc kịch bản theo nhóm: Té ngã/ }),
    );

    await waitFor(() => {
      expect(screen.queryByText("Tăng nhịp tim")).not.toBeInTheDocument();
    });
    expect(screen.getByText("Té ngã nặng")).toBeInTheDocument();
  });

  it("navigates to /session with scenario + device on Run (non-critical)", async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Tăng nhịp tim");

    // Warning-severity card bypasses the confirm dialog.  Use the
    // accessible name (aria-label) which takes the form
    // "Chạy kịch bản <name> trong phiên".
    const runWarningButton = screen.getByRole("button", {
      name: /Chạy kịch bản Tăng nhịp tim trong phiên/,
    });
    await user.click(runWarningButton);

    expect(navigateSpy).toHaveBeenCalledTimes(1);
    const navigatedTo = navigateSpy.mock.calls[0][0] as string;
    expect(navigatedTo).toContain("/session?");
    expect(navigatedTo).toContain("scenario=vitals-tachy");
    // First device gets auto-selected by the page's effect.
    expect(navigatedTo).toMatch(/device=dev-1/);
  });

  it("opens a critical-severity confirm before running", async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Té ngã nặng");

    const runCriticalButton = screen.getByRole("button", {
      name: /Chạy kịch bản Té ngã nặng trong phiên/,
    });
    await user.click(runCriticalButton);

    // Critical confirm should mount.
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(navigateSpy).not.toHaveBeenCalled();

    // Confirm → navigate.
    await user.click(screen.getByRole("button", { name: /Mở Phiên mô phỏng/ }));

    await waitFor(() => {
      expect(navigateSpy).toHaveBeenCalledTimes(1);
    });
    expect(navigateSpy.mock.calls[0][0]).toContain("scenario=fall-hard");
  });

  it("expands a card to reveal key signals + follow-up", async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Té ngã nặng");

    // Collapsed: Acc peak label (in keySignals) is NOT rendered yet.
    expect(screen.queryByText("Acc peak")).not.toBeInTheDocument();
    expect(screen.queryByText(/Side-effect khi áp dụng/)).not.toBeInTheDocument();

    const expandButton = screen.getByRole("button", {
      name: /Xem chi tiết kịch bản Té ngã nặng/,
    });
    await user.click(expandButton);

    // Expanded: keySignals + follow-up strip + expected outcome surface.
    await waitFor(() => {
      expect(screen.getByText("Acc peak")).toBeInTheDocument();
    });
    expect(screen.getByText(/Side-effect khi áp dụng/)).toBeInTheDocument();
    expect(screen.getByText(/Kết quả kỳ vọng/)).toBeInTheDocument();

    // Toggle button now reads "Ẩn chi tiết".
    expect(
      screen.getByRole("button", { name: /Ẩn chi tiết kịch bản Té ngã nặng/ }),
    ).toBeInTheDocument();
  });
});
