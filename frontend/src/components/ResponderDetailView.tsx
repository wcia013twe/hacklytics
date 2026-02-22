import { Camera, X } from 'lucide-react';
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
                    {/* Live Video Feed */}
                    <div className="flex-1 w-full bg-black relative overflow-hidden">
                        {/* Scanlines */}
                        <div className="absolute inset-0 opacity-10 mix-blend-overlay pointer-events-none z-10" style={{ backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 2px, #000 2px, #000 4px)' }}></div>

                        <img
                            src={responder.body_cam_url}
                            alt={`${responder.name} Live Feed`}
                            className="w-full h-full object-cover"
                            onError={(e) => {
                                (e.target as HTMLImageElement).style.display = 'none';
                            }}
                        />

                        {/* Crosshair Overlay */}
                        <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-10">
                            <div className="w-16 h-16 border border-slate-600/30 rounded-full flex items-center justify-center relative">
                                <div className="absolute w-full h-[1px] bg-slate-600/30" />
                                <div className="absolute h-full w-[1px] bg-slate-600/30" />
                            </div>
                        </div>

                        <span className="absolute bottom-4 right-4 text-slate-500 font-mono text-[10px] tracking-[0.3em] uppercase bg-black/50 px-2 py-1 border border-slate-800 z-10">
                            LIVE STREAM — {responder.name}
                        </span>
                    </div>
                </div>

            </div>


        </div>
    );
}
