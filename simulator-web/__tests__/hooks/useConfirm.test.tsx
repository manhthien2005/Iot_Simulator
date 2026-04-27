import { describe, expect, it, vi } from "vitest";
import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useRef } from "react";
import { useConfirm, type ConfirmOptions } from "../../src/hooks/useConfirm";

// ---------------------------------------------------------------------------
// useConfirm — Module G.2 smoke tests.
//
// Strategy: render a tiny harness component that exposes the hook's
// `confirm()` function via an imperative button click.  The pending
// promise is captured into a ref so the test can `await` it after
// driving the dialog UI.
// ---------------------------------------------------------------------------

function Harness({
  options,
  onResolved,
}: {
  options: ConfirmOptions;
  onResolved: (value: boolean) => void;
}) {
  const [confirm, dialog] = useConfirm();
  const promiseRef = useRef<Promise<boolean> | null>(null);

  return (
    <div>
      <button
        type="button"
        onClick={() => {
          const p = confirm(options);
          promiseRef.current = p;
          // Funnel resolution back to the test.
          p.then(onResolved);
        }}
      >
        OPEN
      </button>
      {dialog}
    </div>
  );
}

describe("useConfirm", () => {
  it("does not render the dialog before confirm() is called", () => {
    const onResolved = vi.fn();
    render(
      <Harness
        options={{ title: "T", description: "D" }}
        onResolved={onResolved}
      />,
    );

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("opens the dialog with the provided title + description", async () => {
    const user = userEvent.setup();
    const onResolved = vi.fn();
    render(
      <Harness
        options={{
          title: "Khôi phục mặc định?",
          description: "Thao tác sẽ xoá runtime.json.",
          confirmLabel: "Khôi phục",
        }}
        onResolved={onResolved}
      />,
    );

    await user.click(screen.getByRole("button", { name: "OPEN" }));

    const dialog = await screen.findByRole("dialog");
    expect(dialog).toBeInTheDocument();
    expect(screen.getByText("Khôi phục mặc định?")).toBeInTheDocument();
    expect(screen.getByText("Thao tác sẽ xoá runtime.json.")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Khôi phục" }),
    ).toBeInTheDocument();
  });

  it("resolves true when the confirm button is clicked", async () => {
    const user = userEvent.setup();
    let resolved: boolean | null = null;
    render(
      <Harness
        options={{
          title: "T",
          description: "D",
          confirmLabel: "Xác nhận",
        }}
        onResolved={(v) => {
          resolved = v;
        }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "OPEN" }));
    await user.click(screen.getByRole("button", { name: "Xác nhận" }));

    // RTL flushes pending microtasks via user-event already, but allow
    // a tick so the promise's .then handler runs.
    await act(async () => {
      await Promise.resolve();
    });

    expect(resolved).toBe(true);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("resolves false when the cancel button is clicked", async () => {
    const user = userEvent.setup();
    let resolved: boolean | null = null;
    render(
      <Harness
        options={{ title: "T", description: "D" }}
        onResolved={(v) => {
          resolved = v;
        }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "OPEN" }));
    await user.click(screen.getByRole("button", { name: "Hủy" }));

    await act(async () => {
      await Promise.resolve();
    });

    expect(resolved).toBe(false);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("resolves false on Escape", async () => {
    const user = userEvent.setup();
    let resolved: boolean | null = null;
    render(
      <Harness
        options={{ title: "T", description: "D" }}
        onResolved={(v) => {
          resolved = v;
        }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "OPEN" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    await user.keyboard("{Escape}");

    await act(async () => {
      await Promise.resolve();
    });

    expect(resolved).toBe(false);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
