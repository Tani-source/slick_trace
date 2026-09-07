import React from 'react';
import { useUiStore } from '../state/uiStore';
import { Map, Activity, ListFilter, Trophy, ChevronLeft, ChevronRight } from 'lucide-react';

export const Sidebar: React.FC = () => {
  const { activeTab, setActiveTab, sidebarOpen, setSidebarOpen } = useUiStore();

  const tabs = [
    { id: 'input', label: 'Inputs', icon: Map },
    { id: 'pipeline', label: 'Pipeline', icon: Activity },
    { id: 'shortlist', label: 'Shortlist', icon: ListFilter },
    { id: 'results', label: 'Results', icon: Trophy },
  ] as const;

  return (
    <div className={`flex flex-col bg-gray-900 border-r border-gray-800 transition-all duration-300 ${sidebarOpen ? 'w-64' : 'w-16'}`}>
      <div className="flex items-center justify-between p-4 border-b border-gray-800">
        {sidebarOpen && <h1 className="text-xl font-bold text-white tracking-wide">SlickTrace</h1>}
        <button onClick={() => setSidebarOpen(!sidebarOpen)} className="text-gray-400 hover:text-white transition-colors">
          {sidebarOpen ? <ChevronLeft size={20} /> : <ChevronRight size={20} />}
        </button>
      </div>
      
      <nav className="flex-1 py-4">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`w-full flex items-center px-4 py-3 mb-1 transition-colors ${activeTab === tab.id ? 'bg-blue-600/20 text-blue-400 border-r-2 border-blue-500' : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'}`}
          >
            <tab.icon size={20} className="min-w-[20px]" />
            {sidebarOpen && <span className="ml-3 font-medium">{tab.label}</span>}
          </button>
        ))}
      </nav>
    </div>
  );
};
