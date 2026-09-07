import { create } from 'zustand';
import type { TabId } from '../types/contracts';

interface UIState {
  activeTab: TabId;
  collapsed: boolean;
  layerToggles: {
    aisTracks: boolean;
    slick: boolean;
    releasePoints: boolean;
    simulatedDrift: boolean;
  };
  splitView: boolean;
  maximize: boolean;

  setActiveTab: (tab: TabId) => void;
  toggleCollapsed: () => void;
  toggleLayer: (layer: keyof UIState['layerToggles']) => void;
  setSplitView: (value: boolean) => void;
  toggleMaximize: () => void;
}

export const useUIStore = create<UIState>((set) => ({
  activeTab: 'input',
  collapsed: false,
  layerToggles: {
    aisTracks: true,
    slick: true,
    releasePoints: true,
    simulatedDrift: true,
  },
  splitView: false,
  maximize: false,

  setActiveTab: (tab) => set({ activeTab: tab }),

  toggleCollapsed: () => set((state) => ({ collapsed: !state.collapsed })),

  toggleLayer: (layer) =>
    set((state) => ({
      layerToggles: { ...state.layerToggles, [layer]: !state.layerToggles[layer] },
    })),

  setSplitView: (value) => set({ splitView: value }),

  toggleMaximize: () => set((state) => ({ maximize: !state.maximize })),
}));
