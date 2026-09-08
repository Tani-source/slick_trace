export type DashboardTabId = 'output' | 'input' | 'pipeline' | 'suspects';

export interface NavItem {
  id: DashboardTabId;
  num: number;
  title: string;
  subtitle: string;
}

export interface PipelineStage {
  index: number;
  title: string;
  description: string;
  status: 'done' | 'active' | 'pending';
  percent: number | null; // null renders "—"
  lockedNote?: string;
}
