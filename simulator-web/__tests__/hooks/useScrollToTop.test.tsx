import { describe, expect, it, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router-dom";
import { useEffect } from "react";
import { useScrollToTop } from "../../src/hooks/useScrollToTop";

// ---------------------------------------------------------------------------
// useScrollToTop — Module G.13 smoke tests.
//
// jsdom doesn't implement scrolling, but `window.scrollTo` is callable
// (no-op) so we can spy on it.  We mount the hook inside a memory
// router and assert that switching pathnames triggers a `scrollTo`
// call.  Hash-only changes are out of scope (the hook keys on
// `pathname`, not `key`/`hash`).
// ---------------------------------------------------------------------------

function ConsumerRoute({ navigateTo }: { navigateTo?: string }) {
  useScrollToTop();
  const navigate = useNavigate();
  useEffect(() => {
    if (navigateTo) {
      navigate(navigateTo);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [navigateTo]);
  return null;
}

describe("useScrollToTop", () => {
  beforeEach(() => {
    // Replace scrollTo with a spy on each test — vitest's
    // `restoreMocks: true` will reset between tests.
    vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);
  });

  it("scrolls to top on mount (initial route)", () => {
    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Routes>
          <Route path="/dashboard" element={<ConsumerRoute />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(window.scrollTo).toHaveBeenCalled();
  });

  it("scrolls to top when pathname changes", () => {
    const { rerender } = render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Routes>
          <Route path="/dashboard" element={<ConsumerRoute navigateTo="/devices" />} />
          <Route path="/devices" element={<ConsumerRoute />} />
        </Routes>
      </MemoryRouter>,
    );

    // Initial mount + post-navigate effect → at least 2 calls (one per
    // pathname).  jsdom synchronously runs effects on render.
    expect((window.scrollTo as ReturnType<typeof vi.fn>).mock.calls.length).toBeGreaterThanOrEqual(2);

    rerender(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Routes>
          <Route path="/dashboard" element={<ConsumerRoute navigateTo="/devices" />} />
          <Route path="/devices" element={<ConsumerRoute />} />
        </Routes>
      </MemoryRouter>,
    );
  });
});
