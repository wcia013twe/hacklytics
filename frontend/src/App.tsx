import { useState, useEffect } from 'react';
import { GlobalHeader } from './components/GlobalHeader';
import { SceneContext } from './components/SceneContext';
import { IntelligencePanel } from './components/IntelligencePanel';
import { RespondersList } from './components/RespondersList';
import { ResponderDetailView } from './components/ResponderDetailView';
import { OpsMap } from './components/OpsMap';
import { ImageStack } from './components/ImageStack';
import { useDashboardSocket } from './hooks/useDashboardSocket';
import type { WebSocketPayload } from './types/websocket';

// Mock sequences matching the python server for frontend-only visualization
const MOCK_STATES: Partial<WebSocketPayload>[] = [
  {
    system_status: 'nominal',
    action_command: 'Environment Safe',
    action_reason: 'All telemetry within normal bounds.',
    rag_data: {
      protocol_id: '100',
      hazard_type: 'None',
      source_text: 'Standard monitoring operational. Continue normal duties.',
      actionable_commands: [
        { target: 'ALL UNITS', directive: 'Maintain patrol vectors' }
      ]
    },
    scene_context: {
      entities: [],
      telemetry: { temp_f: 72, trend: 'stable' },
      responders: [
        {
          id: 'R-01', name: 'Alpha-1 (Olsen)', status: 'nominal',
          vitals: { heart_rate: 82, o2_level: 98, aqi: 45 },
          body_cam_url: 'mock_feed_1', thermal_cam_url: 'mock_thermal_1'
        },
        {
          id: 'R-02', name: 'Bravo-2 (Chen)', status: 'nominal',
          vitals: { heart_rate: 76, o2_level: 99, aqi: 42 },
          body_cam_url: 'mock_feed_2', thermal_cam_url: 'mock_thermal_2'
        },
        {
          id: 'R-03', name: 'Charlie-3 (Dixon)', status: 'nominal',
          vitals: { heart_rate: 68, o2_level: 99, aqi: 40 },
          body_cam_url: 'mock_feed', thermal_cam_url: 'mock_thermal'
        },
        {
          id: 'R-04', name: 'Delta-4 (Vasquez)', status: 'nominal',
          vitals: { heart_rate: 85, o2_level: 97, aqi: 41 },
          body_cam_url: 'mock_feed', thermal_cam_url: 'mock_thermal'
        },
        {
          id: 'R-05', name: 'Echo-5 (Hudson)', status: 'nominal',
          vitals: { heart_rate: 90, o2_level: 98, aqi: 45 },
          body_cam_url: 'mock_feed', thermal_cam_url: 'mock_thermal'
        },
        {
          id: 'R-06', name: 'Foxtrot-6 (Hicks)', status: 'nominal',
          vitals: { heart_rate: 88, o2_level: 99, aqi: 42 },
          body_cam_url: 'mock_feed', thermal_cam_url: 'mock_thermal'
        }
      ],
      synthesized_insights: {
        threat_vector: 'Routine patrols active. All zones clear.',
        evacuation_radius_ft: null,
        resource_bottleneck: null,
        max_temp_f: 72,
        max_aqi: 45
      }
    },
  },
  {
    system_status: 'warning',
    action_command: 'Caution: Fire Detected.',
    action_reason: 'Tracking expansion...',
    rag_data: {
      protocol_id: '205',
      hazard_type: 'Combustible Area',
      source_text: 'Small localized fires should be monitored for expansion. Prepare class B extinguishers.',
      actionable_commands: [
        { target: 'Alpha-1', directive: 'Report fire size & trend' },
        { target: 'Charlie-3', directive: 'Monitor sudden AQI drop' }
      ]
    },
    scene_context: {
      entities: [{ name: 'fire', duration_sec: 12, trend: 'expanding' }],
      telemetry: { temp_f: 180, trend: 'rising' },
      responders: [
        {
          id: 'R-01', name: 'Alpha-1 (Olsen)', status: 'warning',
          vitals: { heart_rate: 115, o2_level: 96, aqi: 105 },
          body_cam_url: 'mock_feed_1', thermal_cam_url: 'mock_thermal_1'
        },
        {
          id: 'R-02', name: 'Bravo-2 (Chen)', status: 'nominal',
          vitals: { heart_rate: 81, o2_level: 98, aqi: 60 },
          body_cam_url: 'mock_feed_2', thermal_cam_url: 'mock_thermal_2'
        },
        {
          id: 'R-03', name: 'Charlie-3 (Dixon)', status: 'warning',
          vitals: { heart_rate: 105, o2_level: 94, aqi: 180 },
          body_cam_url: 'mock_feed', thermal_cam_url: 'mock_thermal'
        },
        {
          id: 'R-04', name: 'Delta-4 (Vasquez)', status: 'nominal',
          vitals: { heart_rate: 85, o2_level: 97, aqi: 65 },
          body_cam_url: 'mock_feed', thermal_cam_url: 'mock_thermal'
        },
        {
          id: 'R-05', name: 'Echo-5 (Hudson)', status: 'nominal',
          vitals: { heart_rate: 90, o2_level: 98, aqi: 70 },
          body_cam_url: 'mock_feed', thermal_cam_url: 'mock_thermal'
        },
        {
          id: 'R-06', name: 'Foxtrot-6 (Hicks)', status: 'nominal',
          vitals: { heart_rate: 88, o2_level: 99, aqi: 68 },
          body_cam_url: 'mock_feed', thermal_cam_url: 'mock_thermal'
        }
      ],
      synthesized_insights: {
        threat_vector: 'Multi-vector hazard developing: Expanding fire front near Alpha-1.',
        evacuation_radius_ft: 50,
        resource_bottleneck: 'Alpha-1 isolated near high-heat source.',
        max_temp_f: 180,
        max_aqi: 180
      }
    },
  },
  {
    system_status: 'critical',
    action_command: 'CRITICAL MULTI-HAZARD DETECTED',
    action_reason: 'Imminent BLEVE & Structural Collapse',
    rag_data: {
      protocol_id: '402 / 71A',
      hazard_type: 'Concurrent Hazards',
      source_text: 'Protocol 402: BLEVE occurs when pressurized tanks reach critical temp. Minimum standoff: 100ft. Protocol 71A: Class 4 structural integrity failing in East Wing due to sustained 450F+ temperatures, posing immediate crush risk.',
      actionable_commands: [
        { target: 'Alpha-1', directive: 'EVACUATE NORTH - 100FT (BLEVE)' },
        { target: 'Charlie-3', directive: 'ABORT EAST WING (COLLAPSE RISK)' },
        { target: 'Delta-4', directive: 'Hold perimeter line' }
      ]
    },
    scene_context: {
      entities: [
        { name: 'fire', duration_sec: 85, trend: 'expanding' },
        { name: 'gas_tank', duration_sec: 70, trend: 'static' },
        { name: 'structural_stress', duration_sec: 45, trend: 'expanding' },
      ],
      telemetry: { temp_f: 450, trend: 'rising' },
      responders: [
        {
          id: 'R-01', name: 'Alpha-1 (Olsen)', status: 'critical',
          vitals: { heart_rate: 165, o2_level: 92, aqi: 350 },
          body_cam_url: 'mock_feed_1', thermal_cam_url: 'mock_thermal_1'
        },
        {
          id: 'R-02', name: 'Bravo-2 (Chen)', status: 'warning',
          vitals: { heart_rate: 120, o2_level: 95, aqi: 150 },
          body_cam_url: 'mock_feed_2', thermal_cam_url: 'mock_thermal_2'
        },
        {
          id: 'R-03', name: 'Charlie-3 (Dixon)', status: 'critical',
          vitals: { heart_rate: 155, o2_level: 88, aqi: 420 },
          body_cam_url: 'mock_feed', thermal_cam_url: 'mock_thermal'
        },
        {
          id: 'R-04', name: 'Delta-4 (Vasquez)', status: 'warning',
          vitals: { heart_rate: 110, o2_level: 96, aqi: 160 },
          body_cam_url: 'mock_feed', thermal_cam_url: 'mock_thermal'
        },
        {
          id: 'R-05', name: 'Echo-5 (Hudson)', status: 'nominal',
          vitals: { heart_rate: 95, o2_level: 98, aqi: 110 },
          body_cam_url: 'mock_feed', thermal_cam_url: 'mock_thermal'
        },
        {
          id: 'R-06', name: 'Foxtrot-6 (Hicks)', status: 'nominal',
          vitals: { heart_rate: 92, o2_level: 98, aqi: 115 },
          body_cam_url: 'mock_feed', thermal_cam_url: 'mock_thermal'
        }
      ],
      synthesized_insights: {
        threat_vector: 'CRITICAL MULTI-VECTOR: Propane blast risk + Severe AQI deterioration.',
        evacuation_radius_ft: 100,
        resource_bottleneck: 'Both teams operating in extreme hazard zones.',
        max_temp_f: 450,
        max_aqi: 420
      }
    },
  },
];

function App() {
  const { payload, latencyMs, isConnected } = useDashboardSocket();
  const [useMockData, setUseMockData] = useState(true);
  const [mockIndex, setMockIndex] = useState(0);
  const [selectedResponderId, setSelectedResponderId] = useState<string | null>(null);

  // Cycle mock data every 5 seconds if enabled
  useEffect(() => {
    if (!useMockData) return;
    const interval = setInterval(() => {
      setMockIndex((prev) => (prev + 1) % MOCK_STATES.length);
    }, 5000);
    return () => clearInterval(interval);
  }, [useMockData]);

  // Use real payload if connected and mock is off, otherwise use mock state
  const activeData = (useMockData ? MOCK_STATES[mockIndex] : payload) || MOCK_STATES[0];

  const ragData = activeData.rag_data;
  const sceneData = activeData.scene_context;

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
                isConnected={useMockData ? true : isConnected}
                activeUnit="Rescue-1"
                latencyMs={useMockData ? 24 : latencyMs}
              />
            </div>
            <button
              onClick={() => setUseMockData(!useMockData)}
              className={`text-[9px] px-3 py-2 uppercase tracking-widest font-bold border transition-colors shrink-0 ${useMockData ? 'border-sky-500/50 bg-sky-900/40 text-sky-400' : 'border-slate-700 bg-slate-900/60 text-slate-400 hover:bg-slate-800'}`}
            >
              {useMockData ? 'MOCK ON' : 'MOCK OFF'}
            </button>
          </div>

          <div className="flex-1 overflow-hidden border border-white/10 rounded-none relative">
            <OpsMap
              sceneData={sceneData}
              systemStatus={activeData.system_status}
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
