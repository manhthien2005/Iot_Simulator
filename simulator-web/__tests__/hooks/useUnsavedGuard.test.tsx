import { describe, expect, it, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";
import { useUnsavedGuard } from "../../src/hooks/useUnsavedGuard";

// ---------------------------------------------------------------------------
// useUnsavedGuard — Module G.14 smoke tests.
//
// Verifies the hook attaches a `beforeunload` listener while `dirty`
// is true and removes it on unmount or when `dirty` flips to false.
// ---------------------------------------------------------------------------

function Consumer({ dirty }: { dirty: boolean }) {
  useUnsavedGuard(dirty);
  return null;
}

function makeBeforeUnloadEvent(): BeforeUnloadEvent {
  // jsdom doesn't construct BeforeUnloadEvent natively, so synthesize
  // a plain event with the fields the hook reads/writes.
  const event = new Event("beforeunload", { cancelable: true }) as BeforeUnloadEvent;
  // returnValue is a writable string slot on BeforeUnloadEvent.
  Object.defineProperty(event, "returnValue", {
    writable: true,
    value: "",
  });
  return event;
}

describe("useUnsavedGuard", () => {
  let addSpy: ReturnType<typeof vi.spyOn>;
  let removeSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    addSpy = vi.spyOn(window, "addEventListener");
    removeSpy = vi.spyOn(window, "removeEventListener");
  });

  it("does not attach the listener when dirty=false", () => {
    render(<Consumer dirty={false} />);
    const beforeUnloadAdds = addSpy.mock.calls.filter(
      (call: unknown[]) => call[0] === "beforeunload",
    );
    expect(beforeUnloadAdds).toHaveLength(0);
  });

  it("attaches the listener when dirty=true and removes on unmount", () => {
    const { unmount } = render(<Consumer dirty={true} />);

    const beforeUnloadAdds = addSpy.mock.calls.filter(
      (call: unknown[]) => call[0] === "beforeunload",
    );
    expect(beforeUnloadAdds).toHaveLength(1);

    unmount();

    const beforeUnloadRemoves = removeSpy.mock.calls.filter(
      (call: unknown[]) => call[0] === "beforeunload",
    );
    expect(beforeUnloadRemoves).toHaveLength(1);
  });

  it("listener calls preventDefault + sets returnValue when fired", () => {
    render(<Consumer dirty={true} />);

    const event = makeBeforeUnloadEvent();
    const preventSpy = vi.spyOn(event, "preventDefault");
    window.dispatchEvent(event);

    expect(preventSpy).toHaveBeenCalled();
    expect(event.returnValue).toBe("");
  });

  it("re-attaches when dirty flips false → true", () => {
    const { rerender } = render(<Consumer dirty={false} />);
    rerender(<Consumer dirty={true} />);

    const beforeUnloadAdds = addSpy.mock.calls.filter(
      (call: unknown[]) => call[0] === "beforeunload",
    );
    expect(beforeUnloadAdds.length).toBeGreaterThanOrEqual(1);
  });
});
