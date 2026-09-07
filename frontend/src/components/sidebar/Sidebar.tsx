import { useUIStore } from '../../state/uiStore';
import type { TabId } from '../../types/contracts';
import { Droplet, ListChecks, LayoutGrid, UploadCloud, Workflow } from 'lucide-react';
import TabInput from './TabInput';
import TabPipeline from './TabPipeline';
import TabResults from './TabResults';
import TabShortlist from './TabShortlist';

const TABS: { id: TabId; label: string; Icon: typeof Droplet }[] = [
  { id: 'results', label: 'Results', Icon: LayoutGrid },
  { id: 'input', label: 'Input', Icon: UploadCloud },
  { id: 'pipeline', label: 'Pipeline', Icon: Workflow },
  { id: 'shortlist', label: 'Shortlist', Icon: ListChecks },
];

const TAB_PANELS: Record<TabId, () => JSX.Element> = {
  input: () => <TabInput />,
  pipeline: () => <TabPipeline />,
  results: () => <TabResults />,
  shortlist: () => <TabShortlist />,
};

export default function Sidebar() {
  const activeTab = useUIStore((s) => s.activeTab);
  const collapsed = useUIStore((s) => s.collapsed);
  const setActiveTab = useUIStore((s) => s.setActiveTab);
  const toggleCollapsed = useUIStore((s) => s.toggleCollapsed);

  const ActivePanel = TAB_PANELS[activeTab];

  return (
    <div
      className="flex bg-panel border-r border-border-subtle shrink-0 transition-all duration-200"
      style={{ width: collapsed ? 56 : 340 }}
    >
      <div className="flex flex-col shrink-0 w-14">
        <div className="flex items-center justify-center h-12 border-b border-border-subtle shrink-0">
          <button
            type="button"
            aria-label="Toggle sidebar"
            onClick={toggleCollapsed}
            className="p-2 rounded hover:bg-panel-raised text-text-primary"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
        </div>
        {TABS.map(({ id, label, Icon }) => {
          const isActive = activeTab === id;
          return (
            <button
              key={id}
              type="button"
              onClick={() => setActiveTab(id)}
              title={label}
              className="relative flex items-center justify-center h-12 hover:bg-panel-raised"
              style={{
                borderLeft: isActive ? '2px solid var(--color-accent-teal)' : '2px solid transparent',
              }}
            >
              <Icon
                size={20}
                className={isActive ? 'text-accent-teal' : 'text-text-secondary'}
              />
            </button>
          );
        })}
      </div>

      {!collapsed && (
        <div className="flex flex-col flex-1 min-w-0 border-l border-border-subtle overflow-hidden">
          <div className="flex items-center gap-2 h-12 px-3 shrink-0 border-b border-border-subtle">
            <Droplet className="text-accent-teal" size={18} />
            <span className="text-display font-semibold text-text-primary select-none">SlickTrace</span>
          </div>
          <div className="flex-1 overflow-y-auto">
            <ActivePanel />
          </div>
        </div>
      )}
    </div>
  );
}
