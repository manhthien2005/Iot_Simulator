import { create } from "zustand";

interface SessionStoreState {
  activeSessionId: string | null;
  setActiveSession: (id: string | null) => void;
}

export const useSessionStore = create<SessionStoreState>((set) => ({
  activeSessionId: null,
  setActiveSession: (id) => set({ activeSessionId: id }),
}));
