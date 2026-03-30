import axios from "axios";
import { notify } from "../utils/toast";

const baseURL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8090";
const unavailableToastThreshold = 3;
const unavailableToastCooldownMs = 15_000;

let unavailableFailureStreak = 0;
let lastUnavailableToastAt = 0;
let lastUnavailableMessage = "API Simulator không khả dụng. Hãy kiểm tra backend runtime.";

export const apiClient = axios.create({
  baseURL,
  timeout: 10000,
  headers: { "Content-Type": "application/json" },
});

function isUnavailableError(status: number | undefined) {
  return status == null || status === 503;
}

function resetUnavailableState() {
  unavailableFailureStreak = 0;
  lastUnavailableMessage = "API Simulator không khả dụng. Hãy kiểm tra backend runtime.";
}

function maybeNotifyUnavailable(status: number | undefined) {
  unavailableFailureStreak += 1;
  lastUnavailableMessage =
    status === 503
      ? "API Simulator không khả dụng (503)."
      : "API Simulator không khả dụng. Hãy kiểm tra backend runtime.";

  if (unavailableFailureStreak < unavailableToastThreshold) {
    return;
  }

  const now = Date.now();
  if (now - lastUnavailableToastAt < unavailableToastCooldownMs) {
    return;
  }

  notify.error(lastUnavailableMessage);
  lastUnavailableToastAt = now;
}

apiClient.interceptors.response.use(
  (response) => {
    resetUnavailableState();
    return response;
  },
  (error) => {
    const status = error?.response?.status as number | undefined;
    if (isUnavailableError(status)) {
      maybeNotifyUnavailable(status);
    } else {
      resetUnavailableState();
    }
    return Promise.reject(error);
  }
);
