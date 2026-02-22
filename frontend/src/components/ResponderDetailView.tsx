import { Activity, Camera, HeartPulse, Thermometer, Wind, X } from 'lucide-react';
import type { Responder } from '../types/websocket';

interface ResponderDetailViewProps {
    responder: Responder;
    onClose: () => void;
}

export function ResponderDetailView({ responder, onClose }: ResponderDetailViewProps) {

    const getHeaderColor = (status: string) => {
        switch (status) {
            case 'nominal': return 'bg-sky-900/30 border-sky-500/30 text-sky-400';
            case 'warning': return 'bg-amber-900/30 border-amber-500/50 text-amber-500';
            case 'critical': return 'bg-rose-950/80 border-rose-500/50 text-rose-500';
            default: return 'bg-slate-800 border-slate-700 text-slate-400';
        }
    };

    return (
        <div className="absolute inset-x-8 inset-y-8 z-50 bg-black/60 backdrop-blur-xl border border-white/10 shadow-[0_0_50px_rgba(0,0,0,0.8)] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-200 rounded-none">

            {/* Header */}
            <div className={`p-4 flex items-center justify-between border-b ${getHeaderColor(responder.status)}`}>
                <div className="flex items-center space-x-4">
                    <div className="w-4 h-4 rounded-full bg-current animate-pulse opacity-70"></div>
                    <div>
                        <h2 className="text-xl font-bold tracking-[0.2em] uppercase">{responder.name}</h2>
                        <p className="text-[10px] opacity-80 uppercase tracking-widest font-mono">ID:{responder.id} // OP-STATUS:{responder.status}</p>
                    </div>
                </div>
                <button
                    onClick={onClose}
                    className="p-2 hover:bg-white/10 transition-colors border border-transparent hover:border-white/20"
                >
                    <X className="w-6 h-6" />
                </button>
            </div>

            {/* Media & Feed Section */}
            <div className="flex-1 p-6 relative flex flex-col items-center justify-center">

                {/* Background Grid for military feel */}
                <div className="absolute inset-0 bg-[linear-gradient(rgba(100,116,139,0.1)_1px,transparent_1px),linear-gradient(90deg,rgba(100,116,139,0.1)_1px,transparent_1px)] bg-[size:40px_40px] pointer-events-none" />

                {/* Focal Body Cam */}
                <div className="relative w-full h-full overflow-hidden border border-white/10 flex flex-col bg-black group z-10 shadow-[0_0_30px_rgba(0,0,0,0.5)]">
                    <div className="absolute top-2 left-2 z-20 bg-black/80 border border-slate-700 px-3 py-1 text-[10px] font-mono text-slate-200 flex items-center tracking-widest uppercase">
                        <Camera className="w-3 h-3 mr-2" /> BODY CAM REC // LIVE
                    </div>
                    {/* Mock Video Placeholder */}
                    <div className="flex-1 w-full bg-slate-900 flex items-center justify-center relative overflow-hidden">
                        {/* Scanlines */}
                        <div className="absolute inset-0 opacity-20 mix-blend-overlay pointer-events-none" style={{ backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 2px, #000 2px, #000 4px)' }}></div>

                        <Activity className="w-32 h-32 text-slate-800 absolute opacity-20 animate-pulse" />

                        {/* Crosshair Overlay */}
                        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                            <div className="w-16 h-16 border border-slate-600/30 rounded-full flex items-center justify-center relative">
                                <div className="absolute w-full h-[1px] bg-slate-600/30" />
                                <div className="absolute h-full w-[1px] bg-slate-600/30" />
                            </div>
                        </div>

                        <span className="absolute bottom-4 right-4 text-slate-500 font-mono text-[10px] tracking-[0.3em] uppercase bg-black/50 px-2 py-1 border border-slate-800">
                            ENCRYPTED STREAM ACT-1
                        </span>
                    </div>
                </div>

            </div>

            {/* Telemetry Strip Chart */}
            {/* Telemetry Strip Chart */}
            <div className="h-32 bg-black/80 border-t border-white/10 grid grid-cols-3 divide-x divide-white/10 z-20">

                {/* Vitals: Heart Rate */}
                <div className="flex items-center px-8 space-x-6 relative group overflow-hidden">
                    <div className="absolute bottom-0 left-0 w-full h-[2px] bg-rose-500/50 transform origin-left group-hover:scale-x-100 transition-transform" />
                    <div className="p-4 bg-rose-950/30 border border-rose-900 text-rose-500">
                        <HeartPulse className="w-8 h-8 group-hover:animate-bounce" />
                    </div>
                    <div>
                        <div className="text-slate-500 text-[10px] uppercase tracking-[0.2em] mb-1 font-bold">HRV Monitor</div>
                        <div className="text-4xl font-mono text-rose-400 font-bold flex items-baseline tracking-tighter">
                            {responder.vitals.heart_rate} <span className="text-xs text-rose-500/50 ml-2 tracking-widest font-normal">BPM</span>
                        </div>
                    </div>
                </div>

                {/* Vitals: O2 Level */}
                <div className="flex items-center px-8 space-x-6 relative group overflow-hidden">
                    <div className="absolute bottom-0 left-0 w-full h-[2px] bg-sky-500/50 transform origin-left group-hover:scale-x-100 transition-transform" />
                    <div className="p-4 bg-sky-950/30 border border-sky-900 text-sky-500">
                        <Wind className="w-8 h-8" />
                    </div>
                    <div>
                        <div className="text-slate-500 text-[10px] uppercase tracking-[0.2em] mb-1 font-bold">Blood O2</div>
                        <div className="text-4xl font-mono text-sky-400 font-bold flex items-baseline tracking-tighter">
                            {responder.vitals.o2_level} <span className="text-xs text-sky-500/50 ml-2 tracking-widest font-normal">%</span>
                        </div>
                    </div>
                </div>

                {/* Vitals: Environment AQI */}
                <div className="flex items-center px-8 space-x-6 relative group overflow-hidden">
                    <div className="absolute bottom-0 left-0 w-full h-[2px] bg-amber-500/50 transform origin-left group-hover:scale-x-100 transition-transform" />
                    <div className="p-4 bg-amber-950/30 border border-amber-900 text-amber-500">
                        <Thermometer className="w-8 h-8" />
                    </div>
                    <div>
                        <div className="text-slate-500 text-[10px] uppercase tracking-[0.2em] mb-1 font-bold">Ambient AQI</div>
                        <div className="text-4xl font-mono font-bold flex items-baseline text-amber-400 tracking-tighter">
                            {responder.vitals.aqi} <span className="text-xs text-amber-500/50 ml-2 tracking-widest font-normal">IDX</span>
                        </div>
                    </div>
                </div>

            </div>

        </div>
    );
}
