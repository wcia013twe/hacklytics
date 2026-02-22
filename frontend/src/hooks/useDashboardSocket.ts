import { useState, useEffect } from 'react';
import useWebSocket, { ReadyState } from 'react-use-websocket';
import type { AppState, WebSocketPayload } from '../types/websocket';

const SOCKET_URL = 'ws://127.0.0.1:8080/ws';

export function useDashboardSocket(): AppState {
    const [payload, setPayload] = useState<WebSocketPayload | null>(null);
    const [latencyMs, setLatencyMs] = useState<number>(0);

    const { lastJsonMessage, readyState } = useWebSocket<WebSocketPayload>(SOCKET_URL, {
        shouldReconnect: () => true,
        reconnectInterval: 3000,
    });

    useEffect(() => {
        if (lastJsonMessage) {
            setPayload(lastJsonMessage);

            // Calculate End-to-End Latency
            // The backend timestamp is in seconds (e.g., 1708532455.123)
            // Date.now() is in milliseconds.
            const now = Date.now();
            const payloadTimeMs = lastJsonMessage.timestamp * 1000;
            // If we're using mock data that might have old timestamps, we cap latency to prevent crazy numbers.
            // E.g., if latency > 5 seconds, maybe just show it as is, but usually it'll be small.
            const diff = now - payloadTimeMs;

            // In a real hackathon you might just use absolute value to prevent negative numbers if clocks drift
            setLatencyMs(Math.max(0, diff));
        }
    }, [lastJsonMessage]);

    return {
        payload,
        latencyMs,
        isConnected: readyState === ReadyState.OPEN,
    };
}
