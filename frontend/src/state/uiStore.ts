import { create } from 'zustand';

interface UiState {
  activeTab: 'input' | 'pipeline' | 'shortlist' | 'results';
  setActiveTab: (tab: 'input' | 'pipeline' | 'shortlist' | 'results') => void;
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
}

export const useUiStore = create<UiState>((set) => ({
  activeTab: 'input',
  setActiveTab: (tab) => set({ activeTab: tab }),
  sidebarOpen: true,
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
}));
