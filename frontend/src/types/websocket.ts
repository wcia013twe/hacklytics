export type SystemStatus = 'nominal' | 'warning' | 'critical';

export interface ActionCommand {
    target: string;
    directive: string;
}

export interface SessionHistoryEntry {
    narrative: string;
    hazard_level: string;
    timestamp: number;
}

export interface RagData {
    protocol_id: string;
    hazard_type: string;
    source_text: string;
    source_document?: string;
    actionable_commands?: ActionCommand[];
    similarity_score?: number;
    session_history?: SessionHistoryEntry[];
    temporal_synthesis?: string;
}

export interface Entity {
    name: string;
    duration_sec: number;
    trend: 'expanding' | 'static' | 'diminishing';
}

export interface Telemetry {
    temp_f: number;
    trend: 'rising' | 'falling' | 'stable';
}

export interface Vitals {
    heart_rate: number;
    o2_level: number;
    aqi: number;
}

export interface Responder {
    id: string;
    name: string;
    status: SystemStatus;
    vitals: Vitals;
    body_cam_url: string;
    thermal_cam_url: string;
}

export interface SynthesizedInsights {
    threat_vector: string;
    evacuation_radius_ft: number | null;
    resource_bottleneck: string | null;
    max_temp_f: number;
    max_aqi: number;
}

export interface Detection {
    id: string;
    class_name: string;
    confidence: number; // 0.0 to 1.0
    image_url: string; // URL or Base64 string for the cropped imagery
    timestamp: number;
}

export interface SceneContext {
    entities: Entity[];
    telemetry: Telemetry;
    responders: Responder[];
    synthesized_insights: SynthesizedInsights;
    detections?: Detection[];
}

export interface WebSocketPayload {
    timestamp: number; // e.g., 1708532455.123 (seconds)
    system_status: SystemStatus;
    action_command: string;
    action_reason: string;
    rag_data: RagData;
    scene_context: SceneContext;
}

export interface AppState {
    payload: WebSocketPayload | null;
    latencyMs: number;
    isConnected: boolean;
}
