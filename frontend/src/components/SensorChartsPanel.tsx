import { useEffect, useRef, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { AlertTriangle, Thermometer, Wind } from 'lucide-react';

// ── Thresholds ──
const TEMP_DANGER_F = 150;       // °F — thermal anomaly
const AQI_DANGER = 200;       // AQI index — hazardous air
const AQI_DELTA_ALERT = 80;      // rapid change in AQI over last 5 readings

interface SensorReading {
    time: string;       // HH:MM:SS
    timestamp: number;  // epoch
    temp_f: number;
    aqi: number;
}

interface SensorChartsPanelProps {
    tempF: number;
    aqi: number;
    timestamp: number;
}

export function SensorChartsPanel({ tempF, aqi, timestamp }: SensorChartsPanelProps) {
    const [readings, setReadings] = useState<SensorReading[]>([]);
    const lastTs = useRef(0);

    // Append new readings, deduplicating by timestamp
    useEffect(() => {
        if (!timestamp || timestamp === lastTs.current) return;
        if (tempF === 0 && aqi === 0) return; // skip empty
        lastTs.current = timestamp;

        const d = new Date(timestamp * 1000);
        const time = d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });

        setReadings(prev => {
            const next = [...prev, { time, timestamp, temp_f: tempF, aqi }];
            return next.slice(-60); // Keep last 60 readings (~1 min)
        });
    }, [timestamp, tempF, aqi]);

    // Compute alerts
    const tempAlert = tempF >= TEMP_DANGER_F;

    // AQI delta: compare latest vs 5 readings ago
    let aqiDeltaAlert = false;
    if (readings.length >= 5) {
        const delta = Math.abs(readings[readings.length - 1].aqi - readings[readings.length - 5].aqi);
        aqiDeltaAlert = delta >= AQI_DELTA_ALERT;
    }
    const aqiAbsAlert = aqi >= AQI_DANGER;

    const hasAlert = tempAlert || aqiDeltaAlert || aqiAbsAlert;

    return (
        <div className="flex-1 flex flex-col overflow-y-auto hide-scrollbar p-3 space-y-4">

            {/* Alert Banner */}
            {hasAlert && (
                <div className="bg-rose-950/30 border border-rose-700/50 p-3 flex items-start gap-3 animate-pulse shrink-0">
                    <AlertTriangle className="w-5 h-5 text-rose-500 shrink-0 mt-0.5" />
                    <div className="space-y-1">
                        {tempAlert && (
                            <div className="text-sm font-bold text-rose-400">
                                ⚠ THERMAL ANOMALY — {tempF}°F exceeds {TEMP_DANGER_F}°F threshold
                            </div>
                        )}
                        {aqiAbsAlert && (
                            <div className="text-sm font-bold text-amber-400">
                                ⚠ HAZARDOUS AIR — AQI {aqi} exceeds {AQI_DANGER} threshold
                            </div>
                        )}
                        {aqiDeltaAlert && !aqiAbsAlert && (
                            <div className="text-sm font-bold text-amber-400">
                                ⚠ RAPID GAS CHANGE — AQI delta ≥{AQI_DELTA_ALERT} in last 5 readings
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Temperature Chart */}
            <div className="shrink-0">
                <div className="text-xs uppercase text-rose-400 font-bold tracking-[0.15em] mb-2 flex items-center justify-between">
                    <span className="flex items-center">
                        <Thermometer className="w-4 h-4 mr-2" />
                        Temperature (°F)
                    </span>
                    <span className={`text-lg font-mono font-bold ${tempAlert ? 'text-rose-500 animate-pulse' : 'text-rose-400'}`}>
                        {tempF > 0 ? `${tempF}°F` : '--'}
                    </span>
                </div>
                <div className="h-[180px] bg-slate-900/60 border border-slate-700/40 p-2">
                    {readings.length < 2 ? (
                        <div className="h-full flex items-center justify-center text-slate-700 text-sm font-mono uppercase">
                            Collecting data...
                        </div>
                    ) : (
                        <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={readings} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                                <XAxis
                                    dataKey="time"
                                    tick={{ fontSize: 9, fill: '#64748b' }}
                                    interval="preserveStartEnd"
                                    minTickGap={40}
                                />
                                <YAxis
                                    tick={{ fontSize: 10, fill: '#64748b' }}
                                    domain={['auto', 'auto']}
                                    width={40}
                                />
                                <Tooltip
                                    contentStyle={{ background: '#0f172a', border: '1px solid #334155', fontSize: 12 }}
                                    labelStyle={{ color: '#94a3b8' }}
                                />
                                <ReferenceLine
                                    y={TEMP_DANGER_F}
                                    stroke="#ef4444"
                                    strokeDasharray="4 4"
                                    label={{ value: `${TEMP_DANGER_F}°F`, position: 'right', fill: '#ef4444', fontSize: 10 }}
                                />
                                <Line
                                    type="monotone"
                                    dataKey="temp_f"
                                    stroke="#f87171"
                                    strokeWidth={2}
                                    dot={false}
                                    name="Temp °F"
                                    isAnimationActive={false}
                                />
                            </LineChart>
                        </ResponsiveContainer>
                    )}
                </div>
            </div>

            {/* AQI Chart */}
            <div className="shrink-0">
                <div className="text-xs uppercase text-amber-400 font-bold tracking-[0.15em] mb-2 flex items-center justify-between">
                    <span className="flex items-center">
                        <Wind className="w-4 h-4 mr-2" />
                        Air Quality Index
                    </span>
                    <span className={`text-lg font-mono font-bold ${aqiAbsAlert ? 'text-rose-500 animate-pulse' : 'text-amber-400'}`}>
                        {aqi > 0 ? aqi : '--'}
                    </span>
                </div>
                <div className="h-[180px] bg-slate-900/60 border border-slate-700/40 p-2">
                    {readings.length < 2 ? (
                        <div className="h-full flex items-center justify-center text-slate-700 text-sm font-mono uppercase">
                            Collecting data...
                        </div>
                    ) : (
                        <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={readings} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                                <XAxis
                                    dataKey="time"
                                    tick={{ fontSize: 9, fill: '#64748b' }}
                                    interval="preserveStartEnd"
                                    minTickGap={40}
                                />
                                <YAxis
                                    tick={{ fontSize: 10, fill: '#64748b' }}
                                    domain={[0, 'auto']}
                                    width={40}
                                />
                                <Tooltip
                                    contentStyle={{ background: '#0f172a', border: '1px solid #334155', fontSize: 12 }}
                                    labelStyle={{ color: '#94a3b8' }}
                                />
                                <ReferenceLine
                                    y={AQI_DANGER}
                                    stroke="#f59e0b"
                                    strokeDasharray="4 4"
                                    label={{ value: `AQI ${AQI_DANGER}`, position: 'right', fill: '#f59e0b', fontSize: 10 }}
                                />
                                <Line
                                    type="monotone"
                                    dataKey="aqi"
                                    stroke="#fbbf24"
                                    strokeWidth={2}
                                    dot={false}
                                    name="AQI"
                                    isAnimationActive={false}
                                />
                            </LineChart>
                        </ResponsiveContainer>
                    )}
                </div>
            </div>

            {/* Threshold Reference */}
            <div className="shrink-0 text-[10px] text-slate-600 font-mono space-y-0.5 border-t border-slate-800 pt-2">
                <div>TEMP THRESHOLD: {TEMP_DANGER_F}°F &nbsp;|&nbsp; AQI THRESHOLD: {AQI_DANGER} &nbsp;|&nbsp; AQI Δ ALERT: ±{AQI_DELTA_ALERT}/5 readings</div>
                <div>DATA POINTS: {readings.length}/60 &nbsp;|&nbsp; WINDOW: ~60s</div>
            </div>
        </div>
    );
}
