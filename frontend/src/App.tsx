import { useState, useEffect, useCallback } from 'react';
import { GlobalHeader } from './components/GlobalHeader';
import { SceneContext } from './components/SceneContext';
import { IntelligencePanel } from './components/IntelligencePanel';
import { RespondersList } from './components/RespondersList';
import { ResponderDetailView } from './components/ResponderDetailView';
import { OpsMap } from './components/OpsMap';
import { ImageStack } from './components/ImageStack';
import { useDashboardSocket } from './hooks/useDashboardSocket';

function App() {
  const { payload, latencyMs, isConnected, clearPayload } = useDashboardSocket();
  const [simRunning, setSimRunning] = useState(false);
  const [simLoading, setSimLoading] = useState(false);
  const [selectedResponderId, setSelectedResponderId] = useState<string | null>(null);

  // Toggle simulation via gateway REST API + backend demo
  const toggleSimulation = useCallback(async () => {
    setSimLoading(true);
    try {
      const endpoint = simRunning ? '/sim/stop' : '/sim/start';
      const demoEndpoint = simRunning ? '/demo/stop' : '/demo/start';

      // Clear payload when starting simulation
      if (!simRunning) {
        clearPayload();
      }

      // Call BOTH gateway sim and backend demo
      const [gatewayRes, demoRes] = await Promise.all([
        fetch(`http://127.0.0.1:8080${endpoint}`, { method: 'POST' }).catch(e => {
          console.warn('Gateway not running on :8080, skipping gateway sim:', e);
          return null;
        }),
        fetch(`http://127.0.0.1:8000${demoEndpoint}`, { method: 'POST' }).catch(e => {
          console.warn('Backend demo API not available on :8000, skipping demo:', e);
          return null;
        })
      ]);

      // Use gateway response if available, otherwise demo response
      if (gatewayRes) {
        const data = await gatewayRes.json();
        setSimRunning(data.running ?? !simRunning);
      } else if (demoRes) {
        const data = await demoRes.json();
        setSimRunning((data.status === 'started' || data.running) ?? !simRunning);
      } else {
        console.error('Both gateway and backend demo unavailable');
      }
    } catch (e) {
      console.error('Failed to toggle simulation:', e);
    } finally {
      setSimLoading(false);
    }
  }, [simRunning, clearPayload]);

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

        {/* Left Pillar (3/12): Situations & Response (Logic) */}
        <div className="col-span-3 h-full flex flex-col gap-3 overflow-hidden">

          {/* Unified Logic Accordion */}
          <div className="flex-1 flex flex-col bg-black/40 backdrop-blur-md border border-white/10 overflow-hidden rounded-none">
            <SceneContext data={sceneData} />
            <IntelligencePanel data={ragData} />
          </div>
        </div>

        {/* Center Pillar (6/12): Ops Map (Global View) */}
        <div className="col-span-6 h-full flex flex-col gap-3 min-h-0">
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
            <ImageStack />
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
