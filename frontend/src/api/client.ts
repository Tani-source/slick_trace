import { 
  SlickPolygon, 
  Shortlist, 
  RankedSuspects, 
  PipelineStatus 
} from '../types/contracts';

const API_BASE = 'http://localhost:8000/api';

export class ApiClient {
  static async uploadDataset(type: string, file: File) {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${API_BASE}/datasets/${type}`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) throw new Error(`Upload failed: ${res.statusText}`);
    return res.json();
  }

  static async runPipeline() {
    const res = await fetch(`${API_BASE}/pipeline/run`, { method: 'POST' });
    if (!res.ok) throw new Error(`Pipeline run failed: ${res.statusText}`);
    return res.json();
  }

  static async getStatus(runId: string): Promise<PipelineStatus> {
    const res = await fetch(`${API_BASE}/status?run_id=${runId}`);
    if (!res.ok) throw new Error(`Failed to get status: ${res.statusText}`);
    return res.json();
  }

  static async getSlick(runId: string): Promise<SlickPolygon> {
    const res = await fetch(`${API_BASE}/pipeline/slick?run_id=${runId}`);
    if (!res.ok) throw new Error(`Failed to get slick: ${res.statusText}`);
    return res.json();
  }

  static async getShortlist(runId: string): Promise<Shortlist> {
    const res = await fetch(`${API_BASE}/pipeline/shortlist?run_id=${runId}`);
    if (!res.ok) throw new Error(`Failed to get shortlist: ${res.statusText}`);
    return res.json();
  }

  static async simulate(runId: string) {
    const res = await fetch(`${API_BASE}/pipeline/simulate?run_id=${runId}`, { method: 'POST' });
    if (!res.ok) throw new Error(`Simulate failed: ${res.statusText}`);
    return res.json();
  }

  static async getResults(runId: string): Promise<RankedSuspects> {
    const res = await fetch(`${API_BASE}/results/${runId}`);
    if (!res.ok) throw new Error(`Failed to get results: ${res.statusText}`);
    return res.json();
  }
}
