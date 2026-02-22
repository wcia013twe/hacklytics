import { Database, FileText } from 'lucide-react';
import type { RagData } from '../types/websocket';
import { useEffect, useState } from 'react';

interface IntelligencePanelProps {
    data: RagData | undefined;
}

export function IntelligencePanel({ data }: IntelligencePanelProps) {
    const [isRetrieving, setIsRetrieving] = useState(false);

    // Trigger visual cue when data changes
    useEffect(() => {
        if (data) {
            setIsRetrieving(true);
            const timer = setTimeout(() => setIsRetrieving(false), 1500);
            return () => clearTimeout(timer);
        }
    }, [data]);

    return (
        <div className="flex-[3] flex flex-col p-0 overflow-hidden">
            {/* Palantir-Style Header */}
            <div className="bg-slate-800/80 border-b border-slate-700 px-4 py-3 flex items-center justify-between sticky top-0 z-10">
                <h3 className="text-sm font-bold text-slate-200 uppercase tracking-[0.2em] flex items-center">
                    <Database className={`w-4 h-4 mr-2 ${isRetrieving ? 'text-sky-400 rotate-180 transition-transform duration-700' : 'text-slate-400 transition-transform duration-700'}`} />
                    Response Plans
                </h3>
                <div className={`text-[10px] font-mono uppercase tracking-[0.2em] px-2 py-0.5 border ${isRetrieving ? 'text-sky-400 border-sky-500/50 bg-sky-950/30' : 'text-slate-500 border-slate-700 bg-slate-800'}`}>
                    {isRetrieving ? 'RETRIEVING...' : 'SYNCED'}
                </div>
            </div>

            {!data ? (
                <div className="flex-1 flex items-center justify-center text-slate-600 font-mono text-xs uppercase tracking-widest">
                    No response plans suggested.
                </div>
            ) : (
                <div className="p-3 flex flex-col flex-1 space-y-3 overflow-hidden">
                    <div className="shrink-0">
                        <div className="text-[10px] uppercase text-slate-500 font-bold tracking-[0.2em] mb-2 border-b border-slate-700/50 pb-1 flex justify-between">
                            <span>Hazard Classification</span>
                            <span className="text-sky-500 text-xs">PROTOCOL {data.protocol_id}</span>
                        </div>
                        <div className="text-2xl font-bold text-amber-500 bg-amber-950/20 px-3 py-3 border-l-2 border-amber-500 uppercase tracking-wide">
                            {data.hazard_type}
                        </div>
                    </div>

                    {/* Actionable Commands Map */}
                    {data.actionable_commands && data.actionable_commands.length > 0 && (
                        <div className="flex-1 flex flex-col min-h-[150px]">
                            <div className="text-[10px] uppercase text-slate-500 font-bold tracking-[0.2em] mb-2 border-b border-slate-700/50 pb-1 shrink-0">Active Directives</div>
                            <div className="flex flex-col gap-2 overflow-y-auto pr-2 hide-scrollbar">
                                {data.actionable_commands.map((cmd, idx) => (
                                    <div key={idx} className="bg-sky-950/30 border border-sky-900/50 p-3 flex items-start">
                                        <span className="text-sky-500 font-bold text-xs uppercase tracking-widest mr-3 shrink-0 mt-0.5">
                                            [COMMAND]
                                        </span>
                                        <div className="flex flex-col">
                                            <span className="text-slate-300 font-mono text-sm mb-1 uppercase tracking-wider">{cmd.target}</span>
                                            <span className="text-white font-bold text-lg tracking-wide">{cmd.directive}</span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    <div className="mt-2 shrink-0 h-[160px] flex flex-col">
                        <div className="text-[10px] uppercase text-slate-500 font-bold tracking-[0.2em] mb-2 border-b border-slate-700/50 pb-1 flex items-center justify-between shrink-0 mt-2">
                            <span className="flex items-center">
                                <FileText className="w-3 h-3 mr-2 text-slate-400" /> Source Intelligence
                            </span>
                            {data.source_document && (
                                <span className="flex items-center gap-1 text-sky-400 border border-sky-800/60 bg-sky-950/40 px-2 py-0.5 font-mono normal-case tracking-normal">
                                    <FileText className="w-2.5 h-2.5" />
                                    {data.source_document}
                                </span>
                            )}
                        </div>
                        <blockquote className="border border-slate-700/80 p-4 text-slate-300 bg-slate-900/80 leading-relaxed text-base font-medium flex-1 overflow-y-auto hide-scrollbar">
                            "{data.source_text}"
                        </blockquote>
                    </div>
                </div>
            )}
        </div>
    );
}
