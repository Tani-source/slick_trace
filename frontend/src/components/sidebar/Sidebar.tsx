import { useUiStore } from '../../state/uiStore';
import type { TabId } from '../../state/uiStore';

const NAV_ITEMS = [
  { id: 'output' as TabId, num: 1, title: 'Verdict', subtitle: 'Attribution map & report' },
  { id: 'input' as TabId, num: 2, title: 'Datasets', subtitle: 'Wind, SAR, AIS input' },
  { id: 'pipeline' as TabId, num: 3, title: 'Pipeline', subtitle: 'Execution & logs' },
  { id: 'suspects' as TabId, num: 4, title: 'Shortlist', subtitle: 'Candidate vessels' },
];

export default function Sidebar() {
  const collapsed = useUiStore((s) => s.sidebarCollapsed);
  const activeTab = useUiStore((s) => s.activeTab);
  const toggleCollapsed = useUiStore((s) => s.toggleSidebar);
  const setActiveTab = useUiStore((s) => s.setActiveTab);

  return (
    <div className={`st-rail ${collapsed ? 'collapsed' : ''}`}>
      <div className="st-rail-head">
        <button type="button" className="st-burger" onClick={toggleCollapsed}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="3" y1="12" x2="21" y2="12"></line>
            <line x1="3" y1="6" x2="21" y2="6"></line>
            <line x1="3" y1="18" x2="21" y2="18"></line>
          </svg>
        </button>
        <div className="st-brand">
          <span className="st-mark">❖</span>
          <span className="st-name">SlickTrace</span>
          <span className="st-sub">Beta</span>
        </div>
      </div>
      <div className="st-nav">
        <div className="st-navlabel">WORKFLOW</div>
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            className={`st-navbtn ${activeTab === item.id ? 'active' : ''}`}
            onClick={() => setActiveTab(item.id)}
          >
            <div className="st-num">{item.num}</div>
            <div className="st-label">
              <b>{item.title}</b>
              <span>{item.subtitle}</span>
            </div>
          </button>
        ))}
      </div>
      <div className="st-rail-foot">
        <span className="st-status-dot"></span>
        <span className="st-foot-text">System operational</span>
      </div>
    </div>
  );
}
