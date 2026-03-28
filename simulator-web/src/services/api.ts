import axios from "axios";
import { notify } from "../utils/toast";

const baseURL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8090";

export const apiClient = axios.create({
  baseURL,
  timeout: 10000,
  headers: { "Content-Type": "application/json" },
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status as number | undefined;
    if (!status) {
      notify.error("API Simulator không khả dụng. Hãy kiểm tra backend runtime.");
    } else if (status === 503) {
      notify.error("API Simulator không khả dụng (503).");
    }
    return Promise.reject(error);
  }
);
