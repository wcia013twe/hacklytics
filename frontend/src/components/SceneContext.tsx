import { Flame } from 'lucide-react';
import type { SceneContext as SceneContextType } from '../types/websocket';

interface SceneContextProps {
    data: SceneContextType | undefined;
}

export function SceneContext({ data }: SceneContextProps) {
    if (!data) {
        return (
            <div className="h-full flex flex-col bg-gray-800 rounded-lg border border-gray-700 p-6">
                <h3 className="text-lg font-bold text-gray-400 mb-4 uppercase">Scene Context</h3>
                <div className="flex-1 flex items-center justify-center text-gray-500 italic">
                    Awaiting telemetry...
                </div>
            </div>
        );
    }

    const { entities, synthesized_insights } = data;

    const insights = synthesized_insights; // Fallback mapping could go here if undefined, but our types say it's required.

    return (
        <div className="flex-[2] flex flex-col border-b border-white/10 p-0 overflow-y-auto">
            {/* Palantir-Style Header */}
            <div className="bg-slate-800/80 border-b border-slate-700 px-4 py-3 flex items-center justify-between sticky top-0 z-10">
                <h3 className="text-sm font-bold text-slate-200 uppercase tracking-[0.2em] flex items-center">
                    <Flame className="w-4 h-4 mr-2 text-rose-500" />
                    Scene Aggregation
                </h3>
                <span className="text-xs font-mono text-slate-400">
                    {entities.length} Hazards Detected
                </span>
            </div>

            <div className="p-3 flex flex-col flex-1 space-y-3 text-sm">

                {/* Synthesized Scene Threat Vector */}
                <div>
                    <h4 className="text-[10px] uppercase text-sky-500 font-bold tracking-[0.2em] mb-2 border-b border-slate-700/50 pb-1 flex items-center">
                        AI Threat Vector
                    </h4>
                    <div className="bg-slate-800/50 border-l-2 border-sky-500 p-4 text-xl text-slate-200 leading-snug font-medium">
                        {insights?.threat_vector || "Analyzing scene dynamics..."}
                    </div>
                </div>

                {/* Critical Standoff Context */}
                {insights?.evacuation_radius_ft ? (
                    <div>
                        <h4 className="text-[10px] uppercase text-rose-500 font-bold tracking-[0.2em] mb-2 border-b border-slate-700/50 pb-1">
                            Standoff Radius
                        </h4>
                        <div className="bg-rose-950/20 border border-rose-900/50 p-3 flex items-center justify-between">
                            <span className="text-slate-300 text-sm font-medium">Critical Perimeter</span>
                            <span className="text-4xl font-mono text-rose-500 font-black tracking-tighter">
                                {insights.evacuation_radius_ft}<span className="text-lg text-rose-700 ml-1">FT</span>
                            </span>
                        </div>
                    </div>
                ) : null}

                {/* Resource Bottleneck Context */}
                {insights?.resource_bottleneck ? (
                    <div>
                        <h4 className="text-[10px] uppercase text-amber-500 font-bold tracking-[0.2em] mb-2 border-b border-slate-700/50 pb-1">
                            Resource Alert
                        </h4>
                        <div className="bg-amber-950/20 border-l-2 border-amber-500 p-4">
                            <span className="text-slate-200 text-lg font-medium">
                                {insights.resource_bottleneck}
                            </span>
                        </div>
                    </div>
                ) : null}
            </div>
        </div>
    );
}
