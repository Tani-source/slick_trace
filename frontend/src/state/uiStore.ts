/**
 * uiStore.ts — Zustand store for purely presentational UI state.
 * Owns: active tab, layer toggles, split-view, sidebar collapsed.
 * Never re-derives pipeline results (architecture.md §2.3).
 */

import { create } from "zustand";

export type TabId = "input" | "pipeline" | "suspects" | "output";

export type LayerId = 
  | "slick" 
  | "originEnvelope" 
  | "aisTracks" 
  | "releasePoints" 
  | "driftFootprints";

interface UiState {
  activeTab: TabId;
  sidebarCollapsed: boolean;
  mapMaximized: boolean;
  splitViewOpen: boolean;
  activeLayers: Set<LayerId>;
  highlightedMmsi: string | null;
  timelineExpanded: boolean;
  darkShipEnabled: boolean;
  oilTypeEnabled: boolean;

  // Actions
  setActiveTab: (tab: TabId) => void;
  toggleSidebar: () => void;
  setMapMaximized: (v: boolean) => void;
  setSplitViewOpen: (v: boolean) => void;
  toggleLayer: (layer: LayerId) => void;
  setHighlightedMmsi: (mmsi: string | null) => void;
  setTimelineExpanded: (v: boolean) => void;
  setDarkShipEnabled: (enabled: boolean) => void;
  setOilTypeEnabled: (enabled: boolean) => void;
}

export const useUiStore = create<UiState>((set, get) => ({
  activeTab: "input", // default: Input tab per architecture.md §2.1
  sidebarCollapsed: false,
  mapMaximized: false,
  splitViewOpen: false,
  activeLayers: new Set<LayerId>(["slick", "originEnvelope", "aisTracks", "releasePoints", "driftFootprints"]),
  highlightedMmsi: null,
  timelineExpanded: false,
  darkShipEnabled: false,
  oilTypeEnabled: false,

  setActiveTab: (tab) => set({ activeTab: tab }),

  toggleSidebar: () =>
    set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),

  setMapMaximized: (v) => set({ mapMaximized: v }),

  setSplitViewOpen: (v) => set({ splitViewOpen: v }),

  toggleLayer: (layer) =>
    set((state) => {
      const next = new Set(state.activeLayers);
      if (next.has(layer)) next.delete(layer);
      else next.add(layer);
      return { activeLayers: next };
    }),

  setHighlightedMmsi: (mmsi) => set({ highlightedMmsi: mmsi }),

  setTimelineExpanded: (v) => set({ timelineExpanded: v }),
  
  setDarkShipEnabled: (enabled) => set({ darkShipEnabled: enabled }),
  setOilTypeEnabled: (enabled) => set({ oilTypeEnabled: enabled }),
}));
