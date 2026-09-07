import { create } from 'zustand';
import { PipelineStatus } from '../types/contracts';

interface PipelineState {
  runId: string | null;
  status: PipelineStatus | null;
  error: string | null;
  isPolling: boolean;
  setRunId: (id: string) => void;
  setStatus: (status: PipelineStatus) => void;
  setError: (err: string | null) => void;
  setPolling: (polling: boolean) => void;
}

export const usePipelineStore = create<PipelineState>((set) => ({
  runId: null,
  status: null,
  error: null,
  isPolling: false,
  setRunId: (id) => set({ runId: id }),
  setStatus: (status) => set({ status }),
  setError: (error) => set({ error }),
  setPolling: (isPolling) => set({ isPolling }),
}));
