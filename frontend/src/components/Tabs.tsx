import React from 'react';

export const TabInput: React.FC = () => {
  return (
    <div className="p-6 text-gray-300 h-full flex flex-col">
      <h2 className="text-2xl font-bold text-white mb-6">Data Inputs</h2>
      <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-6 flex-1 flex items-center justify-center">
        <p className="text-gray-500">Input data upload and validation panel (stub)</p>
      </div>
    </div>
  );
};

export const TabPipeline: React.FC = () => {
  return (
    <div className="p-6 text-gray-300 h-full flex flex-col">
      <h2 className="text-2xl font-bold text-white mb-6">Pipeline Execution</h2>
      <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-6 flex-1 flex items-center justify-center">
        <p className="text-gray-500">Pipeline progress and status panel (stub)</p>
      </div>
    </div>
  );
};

export const TabShortlist: React.FC = () => {
  return (
    <div className="p-6 text-gray-300 h-full flex flex-col">
      <h2 className="text-2xl font-bold text-white mb-6">Candidate Shortlist</h2>
      <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-6 flex-1 flex items-center justify-center">
        <p className="text-gray-500">AIS shortlist and anomaly scoring panel (stub)</p>
      </div>
    </div>
  );
};

export const TabResults: React.FC = () => {
  return (
    <div className="p-6 text-gray-300 h-full flex flex-col">
      <h2 className="text-2xl font-bold text-white mb-6">Final Attribution</h2>
      <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-6 flex-1 flex items-center justify-center">
        <p className="text-gray-500">Ranked suspects and detailed metrics (stub)</p>
      </div>
    </div>
  );
};
