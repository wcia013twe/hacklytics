import { Activity, HeartPulse } from 'lucide-react';
import { useRef, useEffect } from 'react';
import type { Responder } from '../types/websocket';

interface RespondersListProps {
    responders: Responder[] | undefined;
    selectedResponderId: string | null;
    onSelectResponder: (id: string) => void;
}

export function RespondersList({ responders, selectedResponderId, onSelectResponder }: RespondersListProps) {
    const scrollContainerRef = useRef<HTMLDivElement>(null);
    const criticalRefs = useRef<{ [key: string]: HTMLButtonElement | null }>({});

    // Effect to detect if any critical responders are out of view, and auto-scroll to the first one
    useEffect(() => {
        if (!responders || !scrollContainerRef.current) return;

        const container = scrollContainerRef.current;

        // Find the first hidden critical card
        const firstHiddenCritical = responders.find(r => {
            if (r.status !== 'critical') return false;
            const el = criticalRefs.current[r.id]; // Use criticalRefs
            if (!el) return false;

            // Check if card is visible vertically
            const containerRect = container.getBoundingClientRect();
            const cardRect = el.getBoundingClientRect();

            const isFullyVisible = (
                cardRect.top >= containerRect.top &&
                cardRect.bottom <= containerRect.bottom
            );
            return !isFullyVisible;
        });

        if (firstHiddenCritical) {
            const el = criticalRefs.current[firstHiddenCritical.id]; // Use criticalRefs
            if (el) {
                // Scroll to bring it into view
                container.scrollTo({
                    top: el.offsetTop - container.offsetTop - 20, // 20px padding
                    behavior: 'smooth'
                });
            }
        }
    }, [responders]);

    if (!responders || responders.length === 0) {
        return (
            <div className="w-full flex items-center justify-center h-full text-slate-600 font-mono text-xs tracking-widest uppercase border border-slate-700 bg-slate-900/50">
                No active responders deployed.
            </div>
        );
    }

    const getStatusTheme = (status: string) => {
        switch (status) {
            case 'nominal': return {
                bg: 'bg-slate-800/80',
                border: 'border-slate-700',
                leftAccent: 'bg-sky-500',
                text: 'text-sky-400',
                dot: 'bg-sky-500'
            };
            case 'warning': return {
                bg: 'bg-amber-950/20',
                border: 'border-amber-500/50',
                leftAccent: 'bg-amber-500',
                text: 'text-amber-500',
                dot: 'bg-amber-500 animate-ping'
            };
            case 'critical': return {
                bg: 'bg-rose-950/40',
                border: 'border-rose-500',
                leftAccent: 'bg-rose-600',
                text: 'text-rose-500',
                dot: 'bg-rose-500 animate-ping'
            };
            default: return {
                bg: 'bg-slate-800/50',
                border: 'border-slate-700',
                leftAccent: 'bg-slate-600',
                text: 'text-slate-400',
                dot: 'bg-slate-500'
            };
        }
    };

    return (
        <div className="w-full h-full flex flex-col gap-3 overflow-hidden">
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-[0.2em] mb-2 sticky top-0 bg-slate-950 py-1 z-20 shrink-0">
                Active Vanguard Elements
            </h3>

            {/* Vertical Flex Container for Right Pillar Sidebar */}
            <div
                ref={scrollContainerRef}
                className="flex flex-col gap-2 overflow-y-auto pb-2 hide-scrollbar flex-1 relative"
            >
                {responders.map((r) => {
                    const isSelected = selectedResponderId === r.id;
                    const theme = getStatusTheme(r.status);

                    return (
                        <button
                            key={r.id}
                            ref={(el) => {
                                if (r.status === 'critical') {
                                    criticalRefs.current[r.id] = el;
                                }
                            }}
                            onClick={() => onSelectResponder(r.id)}
                            className={`relative w-full flex flex-col text-left border overflow-hidden p-0 transition-all duration-200
                                ${theme.bg} ${theme.border}
                                ${isSelected ? 'ring-1 ring-sky-400 brightness-125' : 'hover:brightness-110'}
                            `}
                        >
                            {/* Left Accent Bar mimicking "Response Plans" */}
                            <div className={`absolute left-0 top-0 bottom-0 w-1 ${theme.leftAccent}`} />

                            <div className="p-2.5 pl-4 flex items-center justify-between h-full">
                                <div className="flex items-center space-x-3 shrink-0">
                                    <div className={`w-2.5 h-2.5 rounded-full ${theme.dot}`} />
                                    <span className="font-bold text-slate-200 tracking-wide text-lg truncate max-w-[140px]" title={r.name}>{r.name}</span>
                                </div>

                                <div className="flex items-center space-x-5 text-slate-300 text-sm flex-1 justify-center px-4">
                                    <div className="flex items-center space-x-2">
                                        <HeartPulse className="w-4 h-4 text-rose-500/80" />
                                        <span className="font-mono">{r.vitals.heart_rate} bpm</span>
                                    </div>
                                    <div className="flex items-center space-x-2">
                                        <Activity className="w-4 h-4 text-sky-500/80" />
                                        <span className="font-mono">O2: {r.vitals.o2_level}%</span>
                                    </div>
                                </div>

                                <span className={`text-sm uppercase font-bold tracking-[0.2em] ${theme.text} w-24 text-right shrink-0`}>
                                    {r.status}
                                </span>
                            </div>
                        </button>
                    );
                })}
            </div>
        </div>
    );
}

// Add CSS to index.css to hide the scrollbar for webkit but allow scrolling:
// .hide-scrollbar::-webkit-scrollbar { display: none; }
// .hide-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
