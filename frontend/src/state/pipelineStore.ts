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
import { useUiStore } from './uiStore';

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
  loadDemo: () => Promise<void>;
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

  loadDemo: async () => {
    set({ runningPipeline: true, pollError: null });
    try {
      const { loadDemoScenario } = await import('../api/client');
      const res = await loadDemoScenario();
      if (res && res.run_id) {
        set({
          runId: res.run_id,
          datasets: {
            sar: res.datasets.sar || { status: 'uploaded', file_name: 'demo_scene.tif', provenance: 'illustrative', size_bytes: 2188382 },
            ais: res.datasets.ais || { status: 'uploaded', file_name: 'tracks.csv', provenance: 'illustrative', size_bytes: 2288349 },
            wind: res.datasets.wind || { status: 'uploaded', file_name: 'wind.nc', provenance: 'illustrative', size_bytes: 776296 },
            current: res.datasets.current || { status: 'uploaded', file_name: 'currents.nc', provenance: 'illustrative', size_bytes: 776328 },
          },
          pipelineStatus: null,
          slick: null,
          shortlist: null,
          results: null,
        });
      }
    } catch (err: any) {
      set({ pollError: err?.message || 'Failed to load demo scenario' });
    } finally {
      set({ runningPipeline: false });
    }
  },

  startPipeline: async () => {
    const runId = get().runId;
    if (!runId) return;
    set({ runningPipeline: true, pollError: null });
    // Switch to Pipeline tab immediately so the user sees live stage progression
    try {
      useUiStore.getState().setActiveTab('pipeline');
    } catch {
      /* ignore in tests where uiStore might not be mounted */
    }

    try {
      await runPipeline(runId);
      // Continuous polling loop until completion or failure
      let completed = false;
      let retries = 0;
      while (!completed) {
        await new Promise((r) => setTimeout(r, 1000));
        try {
          const status = await getPipelineStatus(runId);
          set({ pipelineStatus: status, connectionLost: false });
          retries = 0;

          const failedStage = status.stages.find((s) => s.status === 'failed');
          if (failedStage) {
            set({ pollError: `Stage '${failedStage.name}' failed: ${failedStage.detail || 'Internal error'}` });
            completed = true;
            break;
          }

          // Refresh slick polygon as perception completes
          const perceptionDone = status.stages.find((s) => s.name === 'perception')?.status === 'done';
          if (perceptionDone && !get().slick) {
            try {
              const slick = await getSlickPolygon(runId);
              set({ slick });
            } catch {
              /* not ready yet */
            }
          }

          // Check if Stages 0-4 are completed (anomaly_scoring is the terminal stage of stages 0-4)
          const isDone = status.stages.find((s) => s.name === 'anomaly_scoring')?.status === 'done';
          if (isDone) {
            completed = true;
            await get().refreshOutputs();
            try {
              useUiStore.getState().setActiveTab('suspects');
            } catch {
              /* ignore */
            }
            break;
          }
        } catch {
          retries += 1;
          if (retries >= 5) {
            set({ pollError: 'Connection lost while polling pipeline status' });
            completed = true;
            break;
          }
        }
      }
    } catch (err: any) {
      if (err?.status === 404 || err?.message?.includes('404')) {
        set({
          pollError: 'Active run has expired or server restarted. Please click "⚡ Load Demo Scenario" or re-upload datasets to proceed.',
          runId: null,
          datasets: EMPTY_DATASETS,
        });
        try {
          useUiStore.getState().setActiveTab('input');
        } catch {}
      } else {
        set({ pollError: err?.message || 'Failed to start pipeline' });
      }
    } finally {
      set({ runningPipeline: false });
    }
  },

  startSimulation: async () => {
    const runId = get().runId;
    if (!runId) return;
    set({ runningPipeline: true, pollError: null });
    try {
      useUiStore.getState().setActiveTab('pipeline');
    } catch {
      /* ignore */
    }

    try {
      const { runSimulate } = await import('../api/client');
      await runSimulate(runId);
      let completed = false;
      let retries = 0;
      while (!completed) {
        await new Promise((r) => setTimeout(r, 1000));
        try {
          const status = await getPipelineStatus(runId);
          set({ pipelineStatus: status, connectionLost: false });
          retries = 0;

          const failedStage = status.stages.find((s) => s.status === 'failed');
          if (failedStage) {
            set({ pollError: `Stage '${failedStage.name}' failed: ${failedStage.detail || 'Internal error'}` });
            completed = true;
            break;
          }

          const isDone = status.stages.find((s) => s.name === 'verification_matching')?.status === 'done';
          if (isDone) {
            completed = true;
            await get().refreshOutputs();
            try {
              useUiStore.getState().setActiveTab('output');
            } catch {
              /* ignore */
            }
            break;
          }
        } catch {
          retries += 1;
          if (retries >= 5) {
            set({ pollError: 'Connection lost while polling simulation status' });
            completed = true;
            break;
          }
        }
      }
    } catch (err: any) {
      set({ pollError: err?.message || 'Failed to start simulation' });
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
