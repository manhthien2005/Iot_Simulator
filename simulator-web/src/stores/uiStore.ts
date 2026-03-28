import { create } from "zustand";

interface UiStoreState {
  sidebarCollapsed: boolean;
  selectedDeviceId: string | null;
  setSidebarCollapsed: (collapsed: boolean) => void;
  setSelectedDeviceId: (deviceId: string | null) => void;
}

export const useUiStore = create<UiStoreState>((set) => ({
  sidebarCollapsed: false,
  selectedDeviceId: null,
  setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
  setSelectedDeviceId: (deviceId) => set({ selectedDeviceId: deviceId })
}));

