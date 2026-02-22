import { Brain, Flame, Wind, Thermometer, TrendingUp } from 'lucide-react';
import type { Telemetry, SynthesizedInsights } from '../types/websocket';

interface LlmAnalysisPanelProps {
    telemetry?: Telemetry;
    insights?: SynthesizedInsights;
    actionCommand?: string;
    actionReason?: string;
}

export function LlmAnalysisPanel({ telemetry, insights, actionCommand, actionReason }: LlmAnalysisPanelProps) {
    const tempF = telemetry?.temp_f ?? 0;
    const trend = telemetry?.trend ?? 'stable';
    const maxAqi = insights?.max_aqi ?? 0;
    const threatVector = insights?.threat_vector;

    return (
        <div className="h-full flex flex-col bg-black/40 backdrop-blur-md border border-white/10 overflow-hidden">
            {/* Header */}
            <div className="bg-slate-800/80 border-b border-slate-700 px-3 py-2 flex items-center justify-between shrink-0">
                <h3 className="text-[10px] font-bold text-slate-200 uppercase tracking-[0.15em] flex items-center">
                    <Brain className="w-3.5 h-3.5 mr-1.5 text-violet-400" />
                    LLM Analysis
                </h3>
                <div className="text-[8px] font-mono text-violet-400/70 bg-violet-950/30 border border-violet-800/30 px-1.5 py-0.5 uppercase tracking-wider">
                    Live
                </div>
            </div>

            <div className="flex-1 overflow-y-auto hide-scrollbar p-2 space-y-2">

                {/* Sensor Telemetry Strip */}
                <div className="grid grid-cols-2 gap-1.5 shrink-0">
                    <div className="bg-slate-900/60 border border-slate-700/40 p-2">
                        <div className="flex items-center gap-1 mb-1">
                            <Thermometer className="w-3 h-3 text-rose-400" />
                            <span className="text-[8px] uppercase text-slate-500 tracking-wider font-bold">MLX90640</span>
                        </div>
                        <div className="flex items-baseline gap-1">
                            <span className="text-lg font-mono font-bold text-rose-400">{tempF > 0 ? tempF : '--'}</span>
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
                    <div className="bg-slate-900/60 border border-slate-700/40 p-2">
                        <div className="flex items-center gap-1 mb-1">
                            <Wind className="w-3 h-3 text-amber-400" />
                            <span className="text-[8px] uppercase text-slate-500 tracking-wider font-bold">BME680 AQI</span>
                        </div>
                        <div className="flex items-baseline gap-1">
                            <span className="text-lg font-mono font-bold text-amber-400">{maxAqi > 0 ? maxAqi : '--'}</span>
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
                        <div className="text-[9px] uppercase text-violet-400 font-bold tracking-[0.15em] mb-1 flex items-center">
                            <Brain className="w-3 h-3 mr-1" />
                            AI Threat Assessment
                        </div>
                        <div className="bg-violet-950/20 border border-violet-800/30 border-l-2 border-l-violet-500 p-2 text-slate-300 text-xs leading-relaxed">
                            {threatVector}
                        </div>
                    </div>
                )}

                {/* Evacuation Radius */}
                {insights?.evacuation_radius_ft && (
                    <div className="shrink-0 bg-rose-950/20 border border-rose-900/50 p-2 flex items-center justify-between">
                        <span className="text-slate-300 text-[10px] font-medium uppercase tracking-wider">Standoff Radius</span>
                        <span className="text-xl font-mono text-rose-500 font-black tracking-tighter">
                            {insights.evacuation_radius_ft}<span className="text-xs text-rose-700 ml-1">FT</span>
                        </span>
                    </div>
                )}
            </div>
        </div>
    );
}
