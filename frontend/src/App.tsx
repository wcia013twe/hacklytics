import { useState, useEffect, useCallback } from 'react';
import { GlobalHeader } from './components/GlobalHeader';
import { SceneContext } from './components/SceneContext';
import { IntelligencePanel } from './components/IntelligencePanel';
import { RagContextPanel } from './components/RagContextPanel';
import { RespondersList } from './components/RespondersList';
import { ResponderDetailView } from './components/ResponderDetailView';
import { OpsMap } from './components/OpsMap';
import { ImageStack } from './components/ImageStack';
import { useDashboardSocket } from './hooks/useDashboardSocket';

function App() {
  const { payload, latencyMs, isConnected } = useDashboardSocket();
  const [simRunning, setSimRunning] = useState(false);
  const [simLoading, setSimLoading] = useState(false);
  const [selectedResponderId, setSelectedResponderId] = useState<string | null>(null);
  const [leftTab, setLeftTab] = useState<'intel' | 'rag'>('intel');

  // Accumulate scene events from every non-nominal payload
  interface SceneEvent {
    timestamp: number;
    status: string;
    action: string;
    temp_f: number;
    entities: number;
  }
  const [sceneEvents, setSceneEvents] = useState<SceneEvent[]>([]);

  useEffect(() => {
    if (!payload) return;
    const status = payload.system_status;
    // Log every payload that carries meaningful info (non-nominal or has entities)
    const entityCount = payload.scene_context?.entities?.length ?? 0;
    if (status !== 'nominal' || entityCount > 0) {
      setSceneEvents(prev => {
        const event: SceneEvent = {
          timestamp: payload.timestamp,
          status,
          action: payload.action_command || '',
          temp_f: payload.scene_context?.telemetry?.temp_f ?? 0,
          entities: entityCount,
        };
        return [...prev, event].slice(-50); // Keep last 50
      });
    }
  }, [payload]);

  // Toggle simulation via gateway REST API
  const toggleSimulation = useCallback(async () => {
    setSimLoading(true);
    try {
      const endpoint = simRunning ? '/sim/stop' : '/sim/start';
      const res = await fetch(`http://127.0.0.1:8080${endpoint}`, { method: 'POST' });
      const data = await res.json();
      setSimRunning(data.running ?? !simRunning);
    } catch (e) {
      console.error('Failed to toggle simulation:', e);
    } finally {
      setSimLoading(false);
    }
  }, [simRunning]);

  // Check simulation status on mount
  useEffect(() => {
    fetch('http://127.0.0.1:8080/sim/status')
      .then(r => r.json())
      .then(data => setSimRunning(data.running ?? false))
      .catch(() => { });
  }, []);

  const ragData = payload?.rag_data;
  const sceneData = payload?.scene_context;

  return (
    <div className="h-screen w-screen p-2 bg-black text-slate-200 overflow-hidden font-sans tracking-wide">

      {/* Row 2: Three-Pillar Tactical Layout */}
      <div className="h-full grid grid-cols-12 gap-3 overflow-hidden relative z-10 block">

        {/* Left Pillar (4/12): Tabbed Intelligence */}
        <div className="col-span-4 h-full flex flex-col overflow-hidden">

          {/* Tab Bar */}
          <div className="flex shrink-0 bg-black/60 border border-white/10 border-b-0">
            <button
              onClick={() => setLeftTab('intel')}
              className={`flex-1 py-2.5 text-[10px] font-bold uppercase tracking-[0.2em] transition-all ${leftTab === 'intel'
                ? 'text-sky-400 bg-black/40 border-b-2 border-sky-500'
                : 'text-slate-500 hover:text-slate-300 border-b-2 border-transparent'
                }`}
            >
              Intel &amp; Response
            </button>
            <button
              onClick={() => setLeftTab('rag')}
              className={`flex-1 py-2.5 text-[10px] font-bold uppercase tracking-[0.2em] transition-all ${leftTab === 'rag'
                ? 'text-violet-400 bg-black/40 border-b-2 border-violet-500'
                : 'text-slate-500 hover:text-slate-300 border-b-2 border-transparent'
                }`}
            >
              RAG Context
            </button>
          </div>

          {/* Tab Content */}
          <div className="flex-1 flex flex-col bg-black/40 backdrop-blur-md border border-white/10 border-t-0 overflow-hidden rounded-none">
            {leftTab === 'intel' ? (
              <>
                <SceneContext data={sceneData} />
                <IntelligencePanel data={ragData} />
              </>
            ) : (
              <RagContextPanel data={ragData} sceneEvents={sceneEvents} />
            )}
          </div>
        </div>

        {/* Center Pillar (5/12): Ops Map (Global View) */}
        <div className="col-span-5 h-full flex flex-col gap-3 min-h-0">
          {/* Header Row for Center Pillar */}
          <div className="flex items-center justify-between shrink-0">
            <div className="flex-1 mr-4">
              <GlobalHeader
                isConnected={isConnected}
                activeUnit="Rescue-1"
                latencyMs={latencyMs}
              />
            </div>
            <button
              onClick={toggleSimulation}
              disabled={simLoading}
              className={`text-[9px] px-3 py-2 uppercase tracking-widest font-bold border transition-colors shrink-0 ${simRunning
                ? 'border-emerald-500/50 bg-emerald-900/40 text-emerald-400 animate-pulse'
                : 'border-slate-700 bg-slate-900/60 text-slate-400 hover:bg-slate-800 hover:border-sky-600'
                } ${simLoading ? 'opacity-50 cursor-wait' : ''}`}
            >
              {simLoading ? '...' : simRunning ? '■ STOP SIM' : '▶ START SIM'}
            </button>
          </div>

          <div className="flex-1 overflow-hidden border border-white/10 rounded-none relative">
            <OpsMap
              sceneData={sceneData}
              systemStatus={payload?.system_status}
            />
          </div>
        </div>

        {/* Right Pillar (3/12): Data & Imagery (Proof) + Active Units */}
        <div className="col-span-3 h-full flex flex-col gap-3 overflow-hidden">
          {/* Visual Intelligence */}
          <div className="flex-[3] min-h-0 overflow-hidden">
            <ImageStack
              telemetry={sceneData?.telemetry}
              maxAqi={sceneData?.synthesized_insights?.max_aqi}
            />
          </div>

          {/* Vanguard Elements List */}
          <div className="flex-[2] min-h-0 bg-black/40 backdrop-blur-md border border-white/10 rounded-none p-2 overflow-hidden flex flex-col">
            <RespondersList
              responders={sceneData?.responders}
              selectedResponderId={selectedResponderId}
              onSelectResponder={setSelectedResponderId}
            />
          </div>
        </div>
      </div>

      {/* Modal Overlay / Slide-Over for Responder Drill-Down */}
      {selectedResponderId && sceneData?.responders && (
        <ResponderDetailView
          responder={sceneData.responders.find((r) => r.id === selectedResponderId)!}
          onClose={() => setSelectedResponderId(null)}
        />
      )}
    </div>
  );
}

export default App;
