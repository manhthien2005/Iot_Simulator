import { describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Tooltip } from "../../src/components/ui/Tooltip";

// ---------------------------------------------------------------------------
// Tooltip — Module G.15 smoke tests.
//
// We pass `delayMs={0}` so the show-delay fires on the next tick, then
// assert with `findByRole` / `waitFor` which polls.  Using fake timers
// alongside userEvent caused infinite hangs because userEvent's
// internal scheduling depends on the real microtask queue.
// ---------------------------------------------------------------------------

describe("Tooltip", () => {
  it("does not render the bubble before hover", () => {
    render(
      <Tooltip content="Helpful note">
        <button>Hover me</button>
      </Tooltip>,
    );

    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("shows the bubble on hover (delay=0)", async () => {
    const user = userEvent.setup();

    render(
      <Tooltip content="Helpful note" delayMs={0}>
        <button>Hover me</button>
      </Tooltip>,
    );

    await user.hover(screen.getByRole("button", { name: "Hover me" }));

    const bubble = await screen.findByRole("tooltip");
    expect(bubble).toHaveTextContent("Helpful note");
  });

  it("hides on unhover", async () => {
    const user = userEvent.setup();

    render(
      <Tooltip content="Bye" delayMs={0}>
        <button>Hover me</button>
      </Tooltip>,
    );

    const trigger = screen.getByRole("button", { name: "Hover me" });
    await user.hover(trigger);
    await screen.findByRole("tooltip");

    await user.unhover(trigger);
    await waitFor(() => {
      expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
    });
  });

  it("hides on Escape", async () => {
    const user = userEvent.setup();

    render(
      <Tooltip content="Press ESC" delayMs={0}>
        <button>Hover me</button>
      </Tooltip>,
    );

    await user.hover(screen.getByRole("button", { name: "Hover me" }));
    await screen.findByRole("tooltip");

    await user.keyboard("{Escape}");
    await waitFor(() => {
      expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
    });
  });

  it("does not show when disabled", async () => {
    const user = userEvent.setup();

    render(
      <Tooltip content="Hidden" delayMs={0} disabled>
        <button>Trigger</button>
      </Tooltip>,
    );

    await user.hover(screen.getByRole("button", { name: "Trigger" }));

    // Give the would-be timeout a chance to fire — tooltip should
    // remain hidden.
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("wires aria-describedby on the trigger when open", async () => {
    const user = userEvent.setup();

    render(
      <Tooltip content="Described" delayMs={0}>
        <button>Trigger</button>
      </Tooltip>,
    );

    const trigger = screen.getByRole("button", { name: "Trigger" });
    expect(trigger).not.toHaveAttribute("aria-describedby");

    await user.hover(trigger);
    const tooltip = await screen.findByRole("tooltip");
    expect(trigger.getAttribute("aria-describedby")).toBe(tooltip.id);
  });
});
