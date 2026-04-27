import { describe, expect, it, vi, beforeEach } from "vitest";

// Mock the sonner module before importing the SUT so the SUT picks up
// the mocked `toast` namespace.
vi.mock("sonner", () => {
  const success = vi.fn();
  const error = vi.fn();
  const warning = vi.fn();
  const info = vi.fn();
  const promise = vi.fn();
  return {
    toast: { success, error, warning, info, promise },
  };
});

import { toast } from "sonner";
import { runWithToast, notify } from "../../src/utils/toast";

const mockedToast = toast as unknown as {
  success: ReturnType<typeof vi.fn>;
  error: ReturnType<typeof vi.fn>;
  warning: ReturnType<typeof vi.fn>;
  info: ReturnType<typeof vi.fn>;
  promise: ReturnType<typeof vi.fn>;
};

describe("notify (sonner adapter)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("forwards success/error/warning/info to sonner", () => {
    notify.success("ok");
    notify.error("nope");
    notify.warning("careful");
    notify.info("fyi");

    expect(mockedToast.success).toHaveBeenCalledWith("ok");
    expect(mockedToast.error).toHaveBeenCalledWith("nope");
    expect(mockedToast.warning).toHaveBeenCalledWith("careful");
    expect(mockedToast.info).toHaveBeenCalledWith("fyi");
  });
});

describe("runWithToast", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("calls toast.promise with the supplied messages", async () => {
    const value = { id: 7 };
    const result = await runWithToast(Promise.resolve(value), {
      loading: "Đang lưu…",
      success: "Đã lưu.",
      error: "Lưu lỗi.",
    });

    expect(result).toEqual(value);
    expect(mockedToast.promise).toHaveBeenCalledTimes(1);
    const [promiseArg, messagesArg] = mockedToast.promise.mock.calls[0];
    expect(promiseArg).toBeInstanceOf(Promise);
    expect(messagesArg).toMatchObject({
      loading: "Đang lưu…",
      success: "Đã lưu.",
      error: "Lưu lỗi.",
    });
  });

  it("re-throws the underlying error so callers can react", async () => {
    const failure = new Error("boom");
    await expect(
      runWithToast(Promise.reject(failure), {
        loading: "loading",
        success: "ok",
        error: "fail",
      }),
    ).rejects.toThrow("boom");

    // The toast was still scheduled.
    expect(mockedToast.promise).toHaveBeenCalledTimes(1);
  });

  it("supports message functions for success / error", async () => {
    await runWithToast(Promise.resolve({ name: "Alice" }), {
      loading: "loading",
      success: (v) => `Hi ${v.name}`,
      error: (e) => `oops: ${(e as Error).message}`,
    });

    const [, messagesArg] = mockedToast.promise.mock.calls[0];
    expect(typeof messagesArg.success).toBe("function");
    expect(typeof messagesArg.error).toBe("function");
    expect(messagesArg.success({ name: "Alice" })).toBe("Hi Alice");
    expect(messagesArg.error(new Error("x"))).toBe("oops: x");
  });
});
