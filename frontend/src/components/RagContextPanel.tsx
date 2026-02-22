import { Brain, Clock, Layers, Database, Search, Zap, Activity } from 'lucide-react';
import type { RagData } from '../types/websocket';

interface SceneEvent {
    timestamp: number;
    status: string;
    action: string;
    temp_f: number;
    entities: number;
}

interface RagContextPanelProps {
    data: RagData | undefined;
    sceneEvents?: SceneEvent[];
}

export function RagContextPanel({ data, sceneEvents = [] }: RagContextPanelProps) {
    const formatTimestamp = (ts: number) => {
        if (!ts) return '--:--:--';
        const d = new Date(ts * 1000);
        return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
    };

    const hazardColor = (level: string) => {
        switch (level?.toUpperCase()) {
            case 'CRITICAL': return 'text-rose-500 bg-rose-950/30 border-rose-800/50';
            case 'HIGH': return 'text-orange-500 bg-orange-950/30 border-orange-800/50';
            case 'MODERATE': return 'text-amber-500 bg-amber-950/30 border-amber-800/50';
            default: return 'text-slate-400 bg-slate-800/30 border-slate-700/50';
        }
    };

    const statusColor = (status: string) => {
        switch (status) {
            case 'critical': return 'text-rose-500 bg-rose-950/40 border-rose-700/50';
            case 'warning': return 'text-amber-500 bg-amber-950/40 border-amber-700/50';
            default: return 'text-sky-400 bg-sky-950/30 border-sky-700/50';
        }
    };

    return (
        <div className="flex-1 flex flex-col overflow-y-auto hide-scrollbar p-3 space-y-4">

            {/* ── Scene Event Timeline (always visible) ── */}
            <div className="shrink-0">
                <div className="text-[10px] uppercase text-violet-400 font-bold tracking-[0.2em] mb-2 flex items-center">
                    <Activity className="w-3 h-3 mr-2" />
                    Scene Event Log
                    {sceneEvents.length > 0 && (
                        <span className="ml-2 text-[9px] text-violet-400/60 bg-violet-950/30 border border-violet-800/30 px-1.5 py-0.5 font-mono">
                            {sceneEvents.length} EVENTS
                        </span>
                    )}
                </div>

                {sceneEvents.length === 0 ? (
                    <div className="bg-slate-900/40 border border-slate-700/40 p-4 text-center text-slate-600 text-xs font-mono uppercase tracking-wider">
                        No scene events captured yet
                    </div>
                ) : (
                    <div className="flex flex-col gap-1 max-h-[280px] overflow-y-auto hide-scrollbar">
                        {[...sceneEvents].reverse().map((evt, i) => (
                            <div key={i} className="bg-slate-900/60 border border-slate-700/40 px-2.5 py-1.5 flex items-center gap-2 text-xs hover:border-violet-700/30 transition-colors">
                                <span className="text-[9px] font-mono text-slate-500 shrink-0">
                                    {formatTimestamp(evt.timestamp)}
                                </span>
                                <span className={`text-[8px] font-bold uppercase tracking-wider px-1.5 py-0.5 border shrink-0 ${statusColor(evt.status)}`}>
                                    {evt.status}
                                </span>
                                <span className="text-slate-500 text-[9px] font-mono shrink-0">
                                    {evt.temp_f > 0 ? `${evt.temp_f}°F` : '--'}
                                </span>
                                {evt.entities > 0 && (
                                    <span className="text-rose-400/70 text-[9px] font-mono shrink-0">
                                        {evt.entities} obj
                                    </span>
                                )}
                                {evt.action && (
                                    <span className="text-slate-400 text-[9px] truncate">
                                        {evt.action}
                                    </span>
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* ── RAG Intelligence (shows when RAG data available) ── */}
            {data && (
                <>
                    {/* Pipeline Status */}
                    <div className="shrink-0">
                        <div className="text-[10px] uppercase text-violet-400 font-bold tracking-[0.2em] mb-2 flex items-center">
                            <Zap className="w-3 h-3 mr-2" />
                            Pipeline Status
                        </div>
                        <div className="grid grid-cols-3 gap-2">
                            <div className="bg-slate-900/60 border border-slate-700/40 p-2 text-center">
                                <div className="text-[8px] uppercase text-slate-500 tracking-wider mb-1">Embedding</div>
                                <div className="text-xs font-mono text-emerald-400">✓ DONE</div>
                            </div>
                            <div className="bg-slate-900/60 border border-slate-700/40 p-2 text-center">
                                <div className="text-[8px] uppercase text-slate-500 tracking-wider mb-1">Vector Search</div>
                                <div className="text-xs font-mono text-emerald-400">✓ DONE</div>
                            </div>
                            <div className="bg-slate-900/60 border border-slate-700/40 p-2 text-center">
                                <div className="text-[8px] uppercase text-slate-500 tracking-wider mb-1">LLM Synthesis</div>
                                <div className="text-xs font-mono text-emerald-400">✓ DONE</div>
                            </div>
                        </div>
                    </div>

                    {/* Protocol Match */}
                    <div className="shrink-0">
                        <div className="text-[10px] uppercase text-violet-400 font-bold tracking-[0.2em] mb-2 flex items-center">
                            <Search className="w-3 h-3 mr-2" />
                            Protocol Match
                        </div>
                        <div className="bg-slate-900/60 border border-violet-800/30 p-3">
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-sm font-bold text-slate-200 font-mono">{data.protocol_id || 'N/A'}</span>
                                {data.similarity_score != null && (
                                    <span className="text-xs font-mono font-bold text-emerald-400 bg-emerald-950/30 border border-emerald-800/50 px-2 py-0.5">
                                        {(data.similarity_score * 100).toFixed(1)}% MATCH
                                    </span>
                                )}
                            </div>
                            {data.similarity_score != null && (
                                <div className="h-1.5 bg-slate-800 overflow-hidden rounded-sm">
                                    <div
                                        className="h-full bg-gradient-to-r from-violet-600 to-emerald-500 transition-all duration-1000"
                                        style={{ width: `${data.similarity_score * 100}%` }}
                                    />
                                </div>
                            )}
                            {data.source_document && (
                                <div className="mt-2 text-[9px] text-slate-500 font-mono flex items-center">
                                    <Database className="w-3 h-3 mr-1 text-slate-600" />
                                    Source: {data.source_document}
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Temporal Synthesis */}
                    {data.temporal_synthesis && (
                        <div className="shrink-0">
                            <div className="text-[10px] uppercase text-violet-400 font-bold tracking-[0.2em] mb-2 flex items-center">
                                <Layers className="w-3 h-3 mr-2" />
                                Temporal Synthesis
                            </div>
                            <div className="bg-violet-950/20 border border-violet-800/30 border-l-2 border-l-violet-500 p-3 text-slate-300 text-sm leading-relaxed">
                                {data.temporal_synthesis}
                            </div>
                        </div>
                    )}

                    {/* Session Memory */}
                    {data.session_history && data.session_history.length > 0 && (
                        <div className="shrink-0">
                            <div className="text-[10px] uppercase text-violet-400 font-bold tracking-[0.2em] mb-2 flex items-center">
                                <Clock className="w-3 h-3 mr-2" />
                                Session Memory
                                <span className="ml-2 text-[9px] text-violet-400/60 bg-violet-950/30 border border-violet-800/30 px-1.5 py-0.5 font-mono">
                                    {data.session_history.length} RECALLED
                                </span>
                            </div>
                            <div className="flex flex-col gap-1.5">
                                {data.session_history.map((entry, i) => (
                                    <div key={i} className="bg-slate-900/60 border border-slate-700/40 p-2.5 hover:border-violet-700/50 transition-colors">
                                        <div className="flex items-center gap-2 mb-1">
                                            <span className="text-[9px] font-mono text-slate-500">
                                                {formatTimestamp(entry.timestamp)}
                                            </span>
                                            <span className={`text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 border ${hazardColor(entry.hazard_level)}`}>
                                                {entry.hazard_level}
                                            </span>
                                        </div>
                                        <p className="text-xs text-slate-400 leading-snug">
                                            {entry.narrative}
                                        </p>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Source Protocol Text */}
                    {data.source_text && (
                        <div className="shrink-0">
                            <div className="text-[10px] uppercase text-violet-400 font-bold tracking-[0.2em] mb-2 flex items-center">
                                <Database className="w-3 h-3 mr-2" />
                                Retrieved Protocol Text
                            </div>
                            <blockquote className="border border-slate-700/80 border-l-2 border-l-violet-500 p-3 text-slate-400 bg-slate-900/80 leading-relaxed text-xs max-h-[200px] overflow-y-auto hide-scrollbar">
                                {data.source_text}
                            </blockquote>
                        </div>
                    )}
                </>
            )}

            {/* Empty RAG state — still shows event log above */}
            {!data && sceneEvents.length === 0 && (
                <div className="flex flex-col items-center justify-center text-slate-600 font-mono text-xs uppercase tracking-widest p-8 text-center">
                    <Brain className="w-8 h-8 mb-3 text-slate-700" />
                    Awaiting RAG cognition cycle...
                    <span className="text-[9px] text-slate-700 mt-1 normal-case tracking-normal">
                        Triggers on MODERATE+ hazard events
                    </span>
                </div>
            )}
        </div>
    );
}
