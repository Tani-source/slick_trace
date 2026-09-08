import { create } from 'zustand';
import type {
  DatasetInfo,
  DatasetType,
  PipelineStatus,
  RankedSuspects,
  Shortlist,
  SlickPolygon,
} from '../types/contracts';
import {
  getPipelineStatus,
  getResults,
  getShortlist,
  getSlickPolygon,
  runPipeline,
  uploadDataset,
} from '../api/client';

const EMPTY_DATASETS: Record<DatasetType, DatasetInfo> = {
  wind: { status: 'not_uploaded' },
  current: { status: 'not_uploaded' },
  sar: { status: 'not_uploaded' },
  ais: { status: 'not_uploaded' },
};

interface PipelineState {
  runId: string | null;
  datasets: Record<DatasetType, DatasetInfo>;
  pipelineStatus: PipelineStatus | null;
  slick: SlickPolygon | null;
  shortlist: Shortlist | null;
  results: RankedSuspects | null;
  runningPipeline: boolean;
  connectionLost: boolean;
  pollError: string | null;

  setRunId: (runId: string) => void;
  setDataset: (type: DatasetType, info: DatasetInfo) => void;
  upload: (type: DatasetType, file: File, provenance: string) => Promise<void>;
  startPipeline: () => Promise<void>;
  startSimulation: () => Promise<void>;
  pollStatus: () => Promise<void>;
  startPolling: (runId: string) => () => void;
  refreshOutputs: () => Promise<void>;
  setConnectionLost: (value: boolean) => void;
  reset: () => void;
}

export const usePipelineStore = create<PipelineState>((set, get) => ({
  runId: null,
  datasets: EMPTY_DATASETS,
  pipelineStatus: null,
  slick: null,
  shortlist: null,
  results: null,
  runningPipeline: false,
  connectionLost: false,
  pollError: null,

  setRunId: (runId) => set({ runId }),

  setDataset: (type, info) =>
    set((state) => ({
      datasets: { ...state.datasets, [type]: info },
      runId: state.runId ?? (info.status === 'uploaded' ? (get().runId ?? null) : state.runId),
    })),

  upload: async (type, file, _provenance) => {
    const currentRunId = get().runId;
    const result = await uploadDataset(type, file, currentRunId || undefined);
    if (result.status === 'uploaded') {
      set({ runId: result.run_id });
      get().setDataset(type, {
        status: 'uploaded',
        provenance: result.provenance,
        file_name: result.file_name,
        size_bytes: result.size_bytes,
        bbox: result.bbox ?? null,
        date_range: result.date_range ?? null,
      });
    }
  },

  startPipeline: async () => {
    const runId = get().runId;
    if (!runId) return;
    set({ runningPipeline: true, pollError: null });
    try {
      await runPipeline(runId);
      await get().pollStatus();
      await get().refreshOutputs();
    } finally {
      set({ runningPipeline: false });
    }
  },

  startSimulation: async () => {
    const runId = get().runId;
    if (!runId) return;
    set({ runningPipeline: true, pollError: null });
    try {
      const { runSimulate } = await import('../api/client');
      await runSimulate(runId);
      await get().pollStatus();
      await get().refreshOutputs();
    } finally {
      set({ runningPipeline: false });
    }
  },

  pollStatus: async () => {
    const runId = get().runId;
    if (!runId) return;
    try {
      const status = await getPipelineStatus(runId);
      set({ pipelineStatus: status, connectionLost: false });
    } catch {
      set({ pollError: 'Failed to fetch pipeline status' });
    }
  },

  startPolling: (runId) => {
    set({ runId });
    let active = true;
    let retries = 0;
    const tick = async () => {
      if (!active) return;
      try {
        const status = await getPipelineStatus(runId);
        set({ pipelineStatus: status, connectionLost: false });
        retries = 0;
      } catch {
        retries += 1;
        if (retries >= 3) {
          set({ connectionLost: true });
        }
      }
      await new Promise((r) => setTimeout(r, 1500));
      if (active) tick();
    };
    void tick();
    return () => {
      active = false;
    };
  },

  refreshOutputs: async () => {
    const runId = get().runId;
    if (!runId) return;
    try {
      const slick = await getSlickPolygon(runId);
      set({ slick });
    } catch {
      /* stage not complete yet */
    }
    try {
      const shortlist = await getShortlist(runId);
      set({ shortlist });
    } catch {
      /* ignore */
    }
    try {
      const results = await getResults(runId);
      set({ results });
    } catch {
      /* ignore */
    }
  },

  setConnectionLost: (value) => set({ connectionLost: value }),

  reset: () =>
    set({
      runId: null,
      datasets: EMPTY_DATASETS,
      pipelineStatus: null,
      slick: null,
      shortlist: null,
      results: null,
      runningPipeline: false,
      connectionLost: false,
      pollError: null,
    }),
}));
