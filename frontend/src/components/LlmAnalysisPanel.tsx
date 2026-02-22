import { Brain, Flame, Wind, Thermometer, TrendingUp, Clock } from 'lucide-react';
import type { Telemetry, SynthesizedInsights } from '../types/websocket';

interface SceneEvent {
    timestamp: number;
    status: string;
    action: string;
    temp_f: number;
    entities: number;
}

interface LlmAnalysisPanelProps {
    telemetry?: Telemetry;
    insights?: SynthesizedInsights;
    sceneEvents?: SceneEvent[];
    actionCommand?: string;
    actionReason?: string;
}

export function LlmAnalysisPanel({ telemetry, insights, sceneEvents = [], actionCommand, actionReason }: LlmAnalysisPanelProps) {

    const formatTimestamp = (ts: number) => {
        if (!ts) return '--:--:--';
        const d = new Date(ts * 1000);
        return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
    };

    const statusBadge = (status: string) => {
        switch (status) {
            case 'critical': return 'text-rose-400 bg-rose-950/40 border-rose-700/50';
            case 'warning': return 'text-amber-400 bg-amber-950/40 border-amber-700/50';
            default: return 'text-sky-400 bg-sky-950/30 border-sky-700/50';
        }
    };

    const tempF = telemetry?.temp_f ?? 0;
    const trend = telemetry?.trend ?? 'stable';
    const maxAqi = insights?.max_aqi ?? 0;
    const threatVector = insights?.threat_vector;

    return (
        <div className="h-full flex flex-col bg-black/40 backdrop-blur-md border border-white/10 overflow-hidden">
            {/* Header */}
            <div className="bg-slate-800/80 border-b border-slate-700 px-4 py-2.5 flex items-center justify-between shrink-0">
                <h3 className="text-[10px] font-bold text-slate-200 uppercase tracking-[0.2em] flex items-center">
                    <Brain className="w-4 h-4 mr-2 text-violet-400" />
                    LLM Analysis
                </h3>
                <div className="text-[9px] font-mono text-violet-400/70 bg-violet-950/30 border border-violet-800/30 px-2 py-0.5 uppercase tracking-wider">
                    Live
                </div>
            </div>

            <div className="flex-1 overflow-y-auto hide-scrollbar p-3 space-y-3">

                {/* Sensor Telemetry Strip */}
                <div className="grid grid-cols-2 gap-2 shrink-0">
                    <div className="bg-slate-900/60 border border-slate-700/40 p-2.5">
                        <div className="flex items-center gap-1.5 mb-1">
                            <Thermometer className="w-3 h-3 text-rose-400" />
                            <span className="text-[8px] uppercase text-slate-500 tracking-wider font-bold">MLX90640</span>
                        </div>
                        <div className="flex items-baseline gap-1">
                            <span className="text-xl font-mono font-bold text-rose-400">{tempF > 0 ? tempF : '--'}</span>
                            <span className="text-[10px] text-rose-500/60">°F</span>
                            <span className={`ml-auto text-[8px] uppercase font-bold px-1 py-0.5 border ${trend === 'rising'
                                    ? 'text-rose-400 border-rose-700/50 bg-rose-950/30'
                                    : 'text-slate-500 border-slate-700 bg-slate-800/30'
                                }`}>
                                {trend === 'rising' && <TrendingUp className="w-2.5 h-2.5 inline mr-0.5" />}
                                {trend}
                            </span>
                        </div>
                    </div>
                    <div className="bg-slate-900/60 border border-slate-700/40 p-2.5">
                        <div className="flex items-center gap-1.5 mb-1">
                            <Wind className="w-3 h-3 text-amber-400" />
                            <span className="text-[8px] uppercase text-slate-500 tracking-wider font-bold">BME680 AQI</span>
                        </div>
                        <div className="flex items-baseline gap-1">
                            <span className="text-xl font-mono font-bold text-amber-400">{maxAqi > 0 ? maxAqi : '--'}</span>
                            <span className="text-[10px] text-amber-500/60">IDX</span>
                            {maxAqi > 150 && (
                                <span className="ml-auto text-[8px] uppercase font-bold text-rose-400 border border-rose-700/50 bg-rose-950/30 px-1 py-0.5 animate-pulse">
                                    <Flame className="w-2.5 h-2.5 inline mr-0.5" />SMOKE
                                </span>
                            )}
                        </div>
                    </div>
                </div>

                {/* AI Threat Assessment */}
                {threatVector && (
                    <div className="shrink-0">
                        <div className="text-[9px] uppercase text-violet-400 font-bold tracking-[0.15em] mb-1.5 flex items-center">
                            <Brain className="w-3 h-3 mr-1.5" />
                            AI Threat Assessment
                        </div>
                        <div className="bg-violet-950/20 border border-violet-800/30 border-l-2 border-l-violet-500 p-3 text-slate-300 text-sm leading-relaxed">
                            {threatVector}
                        </div>
                    </div>
                )}

                {/* Current Action */}
                {actionCommand && actionCommand !== 'CLEAR' && (
                    <div className="shrink-0">
                        <div className="text-[9px] uppercase text-sky-400 font-bold tracking-[0.15em] mb-1.5">
                            Active Directive
                        </div>
                        <div className="bg-sky-950/20 border border-sky-800/30 p-2.5 space-y-1">
                            <div className="text-sm font-bold text-sky-300 uppercase tracking-wider">{actionCommand}</div>
                            {actionReason && (
                                <div className="text-xs text-slate-400 leading-snug">{actionReason}</div>
                            )}
                        </div>
                    </div>
                )}

                {/* Evacuation Radius */}
                {insights?.evacuation_radius_ft && (
                    <div className="shrink-0 bg-rose-950/20 border border-rose-900/50 p-3 flex items-center justify-between">
                        <span className="text-slate-300 text-xs font-medium uppercase tracking-wider">Standoff Radius</span>
                        <span className="text-2xl font-mono text-rose-500 font-black tracking-tighter">
                            {insights.evacuation_radius_ft}<span className="text-sm text-rose-700 ml-1">FT</span>
                        </span>
                    </div>
                )}

                {/* Recent Events Timeline */}
                <div className="shrink-0">
                    <div className="text-[9px] uppercase text-slate-500 font-bold tracking-[0.15em] mb-1.5 flex items-center">
                        <Clock className="w-3 h-3 mr-1.5" />
                        Recent Events
                        {sceneEvents.length > 0 && (
                            <span className="ml-1.5 text-[8px] text-slate-600 font-mono">
                                ({sceneEvents.length})
                            </span>
                        )}
                    </div>
                    {sceneEvents.length === 0 ? (
                        <div className="bg-slate-900/40 border border-slate-700/40 p-3 text-center text-slate-700 text-[10px] font-mono uppercase tracking-wider">
                            Monitoring...
                        </div>
                    ) : (
                        <div className="flex flex-col gap-0.5 max-h-[180px] overflow-y-auto hide-scrollbar">
                            {[...sceneEvents].reverse().slice(0, 15).map((evt, i) => (
                                <div key={i} className="bg-slate-900/50 border border-slate-800/40 px-2 py-1 flex items-center gap-2 text-[10px]">
                                    <span className="font-mono text-slate-600 shrink-0">{formatTimestamp(evt.timestamp)}</span>
                                    <span className={`font-bold uppercase px-1 py-0.5 border text-[8px] shrink-0 ${statusBadge(evt.status)}`}>
                                        {evt.status}
                                    </span>
                                    {evt.entities > 0 && (
                                        <span className="text-rose-400/60">{evt.entities} obj</span>
                                    )}
                                    {evt.action && (
                                        <span className="text-slate-500 truncate">{evt.action}</span>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
