import { Image as ImageIcon, Crosshair, Thermometer, Wind } from 'lucide-react';
import type { Detection, Telemetry } from '../types/websocket';

interface ImageStackProps {
    detections?: Detection[];
    telemetry?: Telemetry;
}

export function ImageStack({ detections = [], telemetry }: ImageStackProps) {
    return (
        <div className="h-full w-full bg-black/40 backdrop-blur-md border border-white/10 flex flex-col p-0 overflow-hidden">
            <h3 className="text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em] px-4 py-3 sticky top-0 bg-black/80 z-10 border-b border-white/10 flex items-center justify-between">
                <span>Visual Intelligence</span>
                <span className="text-sky-500">{detections.length} ACTIVE</span>
            </h3>

            <div className="flex-1 overflow-y-auto p-2 grid grid-cols-2 gap-2 content-start">
                {detections.length === 0 ? (
                    <div className="col-span-2 flex-1 flex flex-col items-center justify-center pointer-events-none opacity-50 py-4">
                        <ImageIcon className="w-6 h-6 text-slate-600 mb-2" />
                        <span className="text-slate-500 font-mono text-[9px] uppercase tracking-widest text-center">
                            No Visual Threats<br />Detected
                        </span>
                    </div>
                ) : (
                    detections.map((det) => (
                        <div key={det.id} className="relative border border-white/10 group overflow-hidden">
                            {/* The YOLO Image Crop */}
                            <img
                                src={det.image_url}
                                alt={det.class_name}
                                className="w-full h-auto object-cover opacity-80 group-hover:opacity-100 transition-opacity grayscale-[30%] contrast-125"
                            />

                            {/* YOLO Bounding Box Overlay Simulation */}
                            <div className="absolute inset-4 border border-rose-500/50 pointer-events-none hidden group-hover:block" />

                            {/* Confidence Score Overlay */}
                            <div className="absolute top-2 left-2 bg-black/80 border border-slate-700 px-2 py-1 flex items-center">
                                <Crosshair className="w-3 h-3 text-rose-500 mr-2" />
                                <span className="text-[9px] font-mono text-slate-200 uppercase font-bold tracking-widest">
                                    {det.class_name.replace('_', ' ')}
                                </span>
                            </div>
                            <div className="absolute bottom-2 right-2 bg-rose-950/80 border border-rose-900 px-2 py-1">
                                <span className="text-[10px] font-mono text-rose-400 font-bold">
                                    {(det.confidence * 100).toFixed(1)}% CONF
                                </span>
                            </div>
                        </div>
                    ))
                )}
            </div>

            {/* Sensor Deltas Panel */}
            <div className="border-t border-white/10 bg-black/60 p-4 shrink-0">
                <h4 className="text-xs font-bold text-slate-400 uppercase tracking-[0.2em] mb-3">
                    Sensor Telemetry Deltas
                </h4>

                <div className="flex flex-col gap-2">
                    {/* MLX90640 Thermal Simulation */}
                    <div className="flex items-center justify-between border-l-2 border-orange-500 pl-3 bg-slate-900/50 py-2 pr-3">
                        <div className="flex items-center text-xs font-mono text-slate-400 uppercase">
                            <Thermometer className="w-4 h-4 text-orange-500 mr-2" />
                            MLX90640
                        </div>
                        <div className={`text-base font-mono font-bold ${(telemetry?.temp_f || 0) > 200 ? 'text-orange-500' : 'text-slate-300'}`}>
                            {telemetry?.temp_f || '--'}°F
                        </div>
                    </div>

                    {/* BME680 VOC / Gas Simulation */}
                    <div className="flex items-center justify-between border-l-2 border-sky-500 pl-3 bg-slate-900/50 py-2 pr-3">
                        <div className="flex items-center text-xs font-mono text-slate-400 uppercase">
                            <Wind className="w-4 h-4 text-sky-500 mr-2" />
                            BME680 VOC
                        </div>
                        <div className="text-base font-mono text-sky-400 font-bold">
                            +12.4% <span className="text-[10px] text-slate-500 ml-1">/min</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
