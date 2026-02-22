import { Map, Scan, Wind } from 'lucide-react';
import type { SceneContext, SystemStatus } from '../types/websocket';

interface OpsMapProps {
    sceneData?: SceneContext;
    systemStatus?: SystemStatus;
}

export function OpsMap({ sceneData, systemStatus = 'nominal' }: OpsMapProps) {
    // Determine the hazard radius based on evacuation config or fallback to AQI for demonstration
    const hazardRadius = sceneData?.synthesized_insights?.evacuation_radius_ft
        ? sceneData.synthesized_insights.evacuation_radius_ft * 2
        : (sceneData?.synthesized_insights?.max_aqi || 0) * 0.5;

    const hasHazard = hazardRadius > 20;

    return (
        <div className="h-full w-full bg-[#0A1128]/80 backdrop-blur-md border border-white/10 flex flex-col relative overflow-hidden">

            {/* Map Header Overlay */}
            <div className="absolute top-0 left-0 right-0 p-4 flex justify-between items-start z-20 pointer-events-none">
                <div>
                    <h3 className="text-xs font-bold text-slate-400 uppercase tracking-[0.2em] flex items-center mb-1">
                        <Map className="w-4 h-4 mr-2" /> Tactical Ops Map
                    </h3>
                    <div className="text-[10px] text-slate-500 font-mono bg-black/50 px-2 py-1 inline-block border border-slate-700">
                        SECTOR: 7G-ALPHA
                    </div>
                </div>

                {hasHazard && (
                    <div className="bg-amber-500/20 border border-amber-500/50 px-3 py-1.5 flex items-center animate-pulse">
                        <Wind className="w-3 h-3 text-amber-500 mr-2" />
                        <span className="text-[10px] text-amber-500 font-bold tracking-widest uppercase">
                            Gas Hazard Detected
                        </span>
                    </div>
                )}
            </div>

            {/* Main Map Area */}
            <div className="flex-1 relative flex items-center justify-center">
                {/* Grid Overlay for military aesthetic */}
                <div className="absolute inset-0 bg-[linear-gradient(rgba(100,116,139,0.15)_1px,transparent_1px),linear-gradient(90deg,rgba(100,116,139,0.15)_1px,transparent_1px)] bg-[size:50px_50px] pointer-events-none" />
                <div className="absolute inset-0 bg-[linear-gradient(rgba(100,116,139,0.05)_1px,transparent_1px),linear-gradient(90deg,rgba(100,116,139,0.05)_1px,transparent_1px)] bg-[size:10px_10px] pointer-events-none" />

                {/* Radar Sweep Effect */}
                <div className="absolute inset-0 pointer-events-none overflow-hidden flex items-center justify-center opacity-30">
                    <div className="w-[800px] h-[800px] rounded-full border border-sky-500/20 border-t-sky-500/80 animate-[spin_4s_linear_infinite]" />
                </div>

                {/* Dynamic Hazard Radius (Yellow Circle) */}
                {hasHazard && (
                    <div
                        className="absolute rounded-full border-2 border-amber-500/50 bg-amber-500/10 flex items-center justify-center transition-all duration-1000 ease-in-out z-10"
                        style={{
                            width: `${hazardRadius * 2}px`,
                            height: `${hazardRadius * 2}px`,
                            boxShadow: '0 0 40px rgba(245, 158, 11, 0.1) inset'
                        }}
                    >
                        {/* Inner danger zone */}
                        {hazardRadius > 100 && (
                            <div className="w-1/2 h-1/2 rounded-full border border-rose-500/30 bg-rose-500/10 animate-pulse" />
                        )}
                    </div>
                )}

                {/* Central Rescue-1 Unit Dot */}
                <div className="relative z-20 flex flex-col items-center justify-center">
                    <div className="relative">
                        {/* Ping animation behind the dot */}
                        <div className={`absolute -inset-2 rounded-full animate-ping opacity-75 ${systemStatus === 'critical' ? 'bg-rose-500' : 'bg-sky-400'}`} />
                        {/* Actual Dot */}
                        <div className={`w-4 h-4 rounded-full border-2 border-white shadow-[0_0_15px_rgba(255,255,255,0.8)] z-10 relative ${systemStatus === 'critical' ? 'bg-rose-500' : 'bg-sky-500'}`} />
                    </div>
                    {/* Unit Label */}
                    <div className="absolute mt-8 whitespace-nowrap bg-black/60 border border-slate-700 px-2 py-0.5 pointer-events-none">
                        <span className="text-[10px] font-mono text-sky-400 font-bold block text-center">RESCUE-1</span>
                    </div>
                </div>
            </div>

            {/* Map Legend Footer */}
            <div className="absolute bottom-0 left-0 right-0 p-2 bg-black/60 border-t border-white/10 flex items-center justify-between pointer-events-none z-20">
                <div className="flex space-x-4">
                    <div className="flex items-center text-[9px] font-mono text-slate-400 uppercase">
                        <div className="w-2 h-2 bg-sky-500 rounded-full mr-2" /> Friendly Unit
                    </div>
                    <div className="flex items-center text-[9px] font-mono text-slate-400 uppercase">
                        <div className="w-2 h-2 border border-amber-500 bg-amber-500/20 rounded-full mr-2" /> Gas/Thermal Hazard
                    </div>
                </div>
                <div className="text-[9px] font-mono text-slate-500 flex items-center">
                    <Scan className="w-3 h-3 text-slate-400 mr-2" /> LIVE TRACKING
                </div>
            </div>
        </div>
    );
}
