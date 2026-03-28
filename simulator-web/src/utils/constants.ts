export const POLL_INTERVALS = {
  vitals: Number(import.meta.env.VITE_POLL_INTERVAL_VITALS ?? 1000),
  devices: Number(import.meta.env.VITE_POLL_INTERVAL_DEVICES ?? 5000)
};

