import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

// ---------------------------------------------------------------------------
// Vitest setup — Module T (smoke tests).
//
// * Loads the jest-dom matchers (`toBeInTheDocument`, `toHaveTextContent`,
//   …) onto Vitest's `expect`.
// * Auto-cleans the React Testing Library DOM between tests so portals
//   (Modal, Tooltip, sonner) don't leak into the next test.
// ---------------------------------------------------------------------------

afterEach(() => {
  cleanup();
});
