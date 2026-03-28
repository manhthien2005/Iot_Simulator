import { create } from "zustand";
import type { VitalsSample } from "../types/vitals";

interface SessionVitalsState {
  activeDeviceId: string | null;
  streamData: VitalsSample[];
  appendSample: (deviceId: string, sample: VitalsSample) => void;
  resetForDevice: (deviceId: string) => void;
  clearAll: () => void;
}

export const useSessionVitalsStore = create<SessionVitalsState>((set) => ({
  activeDeviceId: null,
  streamData: [],
  appendSample: (deviceId, sample) =>
    set((state) => {
      if (state.activeDeviceId !== deviceId) {
        return {
          activeDeviceId: deviceId,
          streamData: [sample],
        };
      }
      const previous = state.streamData[state.streamData.length - 1];
      if (previous && previous.timestamp === sample.timestamp) {
        return state;
      }
      return {
        activeDeviceId: deviceId,
        streamData: [...state.streamData, sample].slice(-120),
      };
    }),
  resetForDevice: (deviceId) =>
    set({
      activeDeviceId: deviceId,
      streamData: [],
    }),
  clearAll: () =>
    set({
      activeDeviceId: null,
      streamData: [],
    }),
}));
