import { create } from "zustand";

interface SessionStoreState {
  activeSessionId: string | null;
  isPaused: boolean;
  selectedDeviceIds: string[];
  streamSpeed: 5 | 15 | 30 | 60;
  setActiveSession: (id: string | null) => void;
  setPaused: (value: boolean) => void;
  toggleDeviceSelection: (id: string) => void;
  setSelectedDeviceIds: (ids: string[]) => void;
  setSpeed: (speed: 5 | 15 | 30 | 60) => void;
}

export const useSessionStore = create<SessionStoreState>((set) => ({
  activeSessionId: null,
  isPaused: false,
  selectedDeviceIds: [],
  streamSpeed: 5,
  setActiveSession: (id) => set({ activeSessionId: id }),
  setPaused: (value) => set({ isPaused: value }),
  toggleDeviceSelection: (id) =>
    set((state) => ({
      selectedDeviceIds: state.selectedDeviceIds.includes(id)
        ? state.selectedDeviceIds.filter((item) => item !== id)
        : [...state.selectedDeviceIds, id]
    })),
  setSelectedDeviceIds: (ids) => set({ selectedDeviceIds: ids }),
  setSpeed: (speed) => set({ streamSpeed: speed })
}));
