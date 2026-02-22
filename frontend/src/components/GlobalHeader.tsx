import { Activity, Wifi, WifiOff } from 'lucide-react';

interface GlobalHeaderProps {
    isConnected: boolean;
    activeUnit: string;
    latencyMs: number;
}

export function GlobalHeader({ isConnected, activeUnit, latencyMs }: GlobalHeaderProps) {
    return (
        <div className="bg-black/90 border-b border-white/10 flex items-center justify-between px-6 py-3 shrink-0 z-50">

            {/* Connection Status */}
            <div className="flex items-center space-x-3">
                <div className="relative flex h-3 w-3">
                    {isConnected && (
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-75"></span>
                    )}
                    <span className={`relative inline-flex rounded-full h-3 w-3 ${isConnected ? 'bg-sky-500' : 'bg-rose-500'}`}></span>
                </div>
                <span className={`text-[10px] tracking-[0.2em] font-bold uppercase ${isConnected ? 'text-sky-400' : 'text-rose-400'}`}>
                    {isConnected ? 'Uplink Established' : 'Signal Lost'}
                </span>
                <div className="text-slate-500 ml-2">
                    {isConnected ? <Wifi className="w-4 h-4" /> : <WifiOff className="w-4 h-4" />}
                </div>
            </div>

            {/* Unit Identifier */}
            <div className="flex items-center space-x-3 text-slate-200">
                <Activity className="w-5 h-5 text-sky-500" />
                <span className="text-sm font-bold tracking-[0.3em] uppercase block mt-0.5">
                    Strategic Command <span className="text-sky-500 ml-2 border-l border-slate-700 pl-2">{activeUnit}</span>
                </span>
            </div>

            {/* Latency Ticker */}
            <div className="font-mono text-[10px] bg-slate-950 border border-slate-800 px-3 py-1 flex items-center space-x-2">
                <span className="uppercase font-bold tracking-[0.2em] text-slate-500 mt-0.5">Latency</span>
                <span className={`font-bold w-12 text-right mt-0.5 ${latencyMs < 100 ? 'text-emerald-400' : latencyMs < 300 ? 'text-amber-400' : 'text-rose-400'}`}>
                    {latencyMs}ms
                </span>
            </div>

        </div>
    );
}
