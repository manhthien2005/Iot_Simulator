import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { SimulatedDevice } from "../../src/types/device";

// ---------------------------------------------------------------------------
// Module C smoke — `<FallLab/>`.
//
// Mocks the eventApi mutations + hook surfaces so we can drive button
// clicks deterministically.  The smoke verifies:
//   * Renders the target dropdown + non-destructive buttons.
//   * Non-critical button (`fall_brief`) calls injectFallEvent directly.
//   * Critical button (`confirmed`) opens the confirm gate first; cancel
//     does NOT fire the mutation; confirm does.
// ---------------------------------------------------------------------------

// `vi.fn` infers a zero-arg signature when initialised with `() => …`,
// which then complains when we pass forwarded arguments below.  Cast
// to a permissive signature: tests only care about `mock.calls`.
const injectEventSpy = vi.fn<(deviceId: string, kind: string) => Promise<void>>(
  async () => undefined,
);
const injectFallEventSpy = vi.fn<
  (deviceId: string, variant: string) => Promise<void>
>(async () => undefined);
const injectSosCancelSpy = vi.fn<(deviceId: string) => Promise<void>>(
  async () => undefined,
);

vi.mock("../../src/services/eventApi", () => ({
  injectEvent: (deviceId: string, kind: string) => injectEventSpy(deviceId, kind),
  injectFallEvent: (deviceId: string, variant: string) =>
    injectFallEventSpy(deviceId, variant),
  injectSosCancel: (deviceId: string) => injectSosCancelSpy(deviceId),
}));

vi.mock("../../src/hooks/useFallState", () => ({
  useFallState: () => ({
    data: {
      fallState: "idle",
      fallVariant: null,
      countdownRemainingSec: 0,
      countdownTotalSec: 30,
    },
  }),
}));

vi.mock("../../src/hooks/useRecentEvents", () => ({
  useRecentEvents: () => ({ data: [] }),
}));

// Quiet sonner during tests — we only care about the spy call for the
// underlying mutation, not the toast surface.
vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
    promise: vi.fn(),
  },
}));

// Import AFTER mocks.
import { FallLab } from "../../src/components/domain/FallLab";

const FAKE_DEVICE: SimulatedDevice = {
  id: "dev-1",
  name: "Watch Alice",
  serialNumber: "SN-001",
  mqttClientId: "mqtt-1",
  deviceType: "smartwatch",
  batteryLevel: 80,
  isOnline: true,
  bindStatus: "bound",
  lastSeenAt: null,
  hasPendingSync: false,
  state: "streaming",
  boundDbDeviceId: 1,
  currentScenarioId: null,
};

function renderLab() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <FallLab devices={[FAKE_DEVICE]} sessionId="sess-1" />
    </QueryClientProvider>,
  );
}

describe("FallLab smoke", () => {
  beforeEach(() => {
    injectEventSpy.mockClear();
    injectFallEventSpy.mockClear();
    injectSosCancelSpy.mockClear();
  });

  it("renders the device selector + key action buttons", () => {
    renderLab();
    expect(
      screen.getByRole("combobox", {
        name: /Chọn thiết bị mục tiêu cho phòng thí nghiệm té ngã/,
      }),
    ).toBeInTheDocument();

    expect(screen.getByRole("button", { name: /Té ngã nhẹ/ })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Té ngã xác nhận/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Không phản hồi/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /SOS thủ công/ }),
    ).toBeInTheDocument();
  });

  it("non-critical button fires injectFallEvent directly (no confirm)", async () => {
    const user = userEvent.setup();
    renderLab();

    await user.click(screen.getByRole("button", { name: /Té ngã nhẹ/ }));

    await waitFor(() => {
      expect(injectFallEventSpy).toHaveBeenCalledTimes(1);
    });
    expect(injectFallEventSpy).toHaveBeenCalledWith("dev-1", "fall_brief");
    // No dialog appeared.
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("critical 'Té ngã xác nhận' opens confirm; cancel does NOT mutate", async () => {
    const user = userEvent.setup();
    renderLab();

    await user.click(screen.getByRole("button", { name: /Té ngã xác nhận/ }));

    const dialog = await screen.findByRole("dialog");
    expect(dialog).toBeInTheDocument();
    expect(injectFallEventSpy).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: /Hủy/ }));

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
    expect(injectFallEventSpy).not.toHaveBeenCalled();
  });

  it("critical 'Té ngã xác nhận' confirm → fires injectFallEvent", async () => {
    const user = userEvent.setup();
    renderLab();

    await user.click(screen.getByRole("button", { name: /Té ngã xác nhận/ }));
    await screen.findByRole("dialog");

    await user.click(
      screen.getByRole("button", { name: /Gửi té ngã xác nhận/ }),
    );

    await waitFor(() => {
      expect(injectFallEventSpy).toHaveBeenCalledTimes(1);
    });
    expect(injectFallEventSpy).toHaveBeenCalledWith("dev-1", "confirmed");
  });
});
