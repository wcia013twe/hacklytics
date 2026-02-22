#!/usr/bin/env python3
"""
Terminal Real-Time Dashboard for RAG Pipeline

Displays live telemetry stream with beautiful ASCII visualization.
No browser needed - pure terminal interface.

Usage:
    python3 scripts/terminal_dashboard.py --scenario growing_warehouse_fire --duration 60
"""

import asyncio
import argparse
import time
import sys
from typing import Dict, List
import httpx

# Terminal colors
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

# Hazard level colors
HAZARD_COLORS = {
    "CLEAR": Colors.GREEN,
    "LOW": Colors.CYAN,
    "MODERATE": Colors.YELLOW,
    "HIGH": Colors.YELLOW + Colors.BOLD,
    "CRITICAL": Colors.RED + Colors.BOLD,
}

RAG_URL = "http://localhost:8001/process"

# Import scenarios from mock_nano_stream
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from mock_nano_stream import SCENARIOS, generate_nano_telemetry


def clear_screen():
    """Clear terminal screen"""
    print("\033[2J\033[H", end="")


def draw_header(scenario_name: str, elapsed: float, total_duration: int, claude_calls: int = 0):
    """Draw dashboard header"""
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}🔥 RAG PIPELINE REAL-TIME MONITOR{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 80}{Colors.END}")
    print(f"Scenario: {Colors.BOLD}{scenario_name}{Colors.END}")
    print(f"Time: {Colors.GREEN}{elapsed:.1f}s{Colors.END} / {total_duration}s")

    # Claude API call counter - always visible
    claude_color = Colors.CYAN if claude_calls > 0 else Colors.YELLOW
    print(f"Claude API Calls: {claude_color}{Colors.BOLD}{claude_calls:4d}{Colors.END}")

    print(f"{Colors.BLUE}{'=' * 80}{Colors.END}\n")


def draw_fire_bar(fire_dominance: float, width: int = 40):
    """Draw fire intensity bar graph"""
    filled = int(fire_dominance * width)
    empty = width - filled

    # Color based on intensity
    if fire_dominance >= 0.8:
        color = Colors.RED + Colors.BOLD
    elif fire_dominance >= 0.5:
        color = Colors.YELLOW
    elif fire_dominance >= 0.2:
        color = Colors.CYAN
    else:
        color = Colors.GREEN

    bar = color + "█" * filled + Colors.END + "░" * empty
    percentage = f"{fire_dominance * 100:5.1f}%"

    return f"[{bar}] {percentage}"


def draw_metrics(metrics: Dict):
    """Draw current metrics"""
    print(f"{Colors.BOLD}CURRENT METRICS:{Colors.END}")
    print(f"  Hazard Level:    {HAZARD_COLORS.get(metrics['hazard'], Colors.END)}{metrics['hazard']:10s}{Colors.END}")
    print(f"  Fire Dominance:  {draw_fire_bar(metrics['fire'])}")
    print(f"  Smoke Opacity:   {metrics['smoke']:5.1%}")
    print(f"  Person Detected: {Colors.YELLOW + '👤 YES' + Colors.END if metrics['person'] else '   NO'}")
    print(f"  Total Latency:   {metrics['latency']:6.2f}ms")

    # Latency breakdown by checkpoint
    if 'breakdown' in metrics:
        breakdown = metrics['breakdown']
        print(f"\n  {Colors.BOLD}Latency Breakdown:{Colors.END}")
        print(f"    Stage 1 (Intake):  {breakdown.get('stage_1_intake_ms', 0):6.2f}ms")
        print(f"    Stage 2 (Reflex):  {breakdown.get('stage_2_reflex_ms', 0):6.2f}ms")
        rag_status = f"{Colors.GREEN}✓ Triggered{Colors.END}" if breakdown.get('stage_3_rag_triggered') else f"{Colors.CYAN}⊘ Skipped{Colors.END}"
        print(f"    Stage 3 (RAG):     {rag_status}")
    print()


def draw_stats(stats: Dict):
    """Draw session statistics"""
    print(f"{Colors.BOLD}SESSION STATS:{Colors.END}")
    print(f"  Total Packets:   {stats['total']:4d}")
    print(f"  Success Rate:    {stats['success_rate']:5.1f}%")
    print(f"  Avg Latency:     {stats['avg_latency']:6.2f}ms")
    print(f"  Peak Fire:       {stats['peak_fire']:5.1%}")
    print(f"  RAG Triggered:   {stats['rag_triggered']:4d} times")
    print(f"  Scenes Detected: {stats['scenes_detected']:4d} (≥2 packets)")

    # Claude API call details
    claude_color = Colors.CYAN if stats['claude_calls'] > 0 else Colors.YELLOW
    fallback_color = Colors.YELLOW if stats['fallback_used'] > 0 else Colors.GREEN
    print(f"  {claude_color}Claude Calls:    {stats['claude_calls']:4d}{Colors.END}")
    print(f"  {fallback_color}Fallback Used:   {stats['fallback_used']:4d}{Colors.END}")

    # Show API usage ratio
    if stats['scenes_detected'] > 0:
        api_ratio = (stats['claude_calls'] / stats['scenes_detected']) * 100
        ratio_color = Colors.GREEN if api_ratio > 80 else Colors.YELLOW if api_ratio > 50 else Colors.RED
        print(f"  {ratio_color}API Usage:       {api_ratio:5.1f}%{Colors.END} (calls/scenes)")
    print()


def draw_history(history: List[Dict], max_entries: int = 10):
    """Draw packet history"""
    print(f"{Colors.BOLD}RECENT PACKETS:{Colors.END}")
    print(f"{'Time':>8s}  {'Hazard':^10s}  {'Fire':>7s}  {'Person':^6s}  {'Latency':>8s}")
    print(f"{'-' * 60}")

    for entry in history[-max_entries:]:
        time_str = f"{entry['elapsed']:7.1f}s"
        hazard_color = HAZARD_COLORS.get(entry['hazard'], Colors.END)
        hazard_str = f"{hazard_color}{entry['hazard']:^10s}{Colors.END}"
        fire_str = f"{entry['fire']:6.2f}"
        person_str = "👤" if entry['person'] else " "
        latency_str = f"{entry['latency']:7.2f}ms"

        print(f"{time_str}  {hazard_str}  {fire_str}  {person_str:^6s}  {latency_str}")


async def stream_with_dashboard(
    scenario_name: str,
    duration: int,
    update_rate: float = 2.0
):
    """Stream scenario with live terminal dashboard"""
    scenario = SCENARIOS[scenario_name]
    duration = duration or scenario["duration_seconds"]

    packets_per_second = update_rate
    total_packets = int(duration * packets_per_second)
    delay = 1.0 / packets_per_second

    start_time = time.time()

    # Stats tracking
    stats = {
        'total': 0,
        'success': 0,
        'success_rate': 0.0,
        'avg_latency': 0.0,
        'peak_fire': 0.0,
        'latencies': [],
        'rag_triggered': 0,
        'scenes_detected': 0,  # Times buffer had >=2 packets
        'claude_calls': 0,      # Actual Claude API calls
        'fallback_used': 0      # Times fallback was used instead of Claude
    }

    # Current metrics
    current_metrics = {
        'hazard': 'CLEAR',
        'fire': 0.0,
        'smoke': 0.0,
        'person': False,
        'latency': 0.0,
        'breakdown': {}
    }

    # History buffer
    history = []

    async with httpx.AsyncClient() as client:
        # Health check
        try:
            response = await client.get("http://localhost:8001/health", timeout=3.0)
            # Start streaming
            clear_screen()
        except Exception as e:
            print(f"{Colors.RED}✗ Cannot reach RAG service{Colors.END}")
            print(f"Error: {e}")
            return

        for step in range(total_packets):
            elapsed = time.time() - start_time
            packet = generate_nano_telemetry(scenario, step, total_packets)

            try:
                # Send packet
                response = await client.post(RAG_URL, json=packet, timeout=5.0)
                response.raise_for_status()
                result = response.json()

                # Update stats
                stats['total'] += 1
                stats['success'] += 1
                stats['success_rate'] = (stats['success'] / stats['total']) * 100

                latency = result.get('total_time_ms', 0)
                stats['latencies'].append(latency)
                stats['avg_latency'] = sum(stats['latencies']) / len(stats['latencies'])

                # Update current metrics
                current_metrics['hazard'] = packet['hazard_level']
                current_metrics['fire'] = packet['scores']['fire_dominance']
                current_metrics['smoke'] = packet['scores']['smoke_opacity']
                current_metrics['person'] = any(obj['label'] == 'person' for obj in packet['tracked_objects'])
                current_metrics['latency'] = latency
                current_metrics['breakdown'] = result.get('latency_breakdown', {})

                # Track RAG triggers
                if current_metrics['breakdown'].get('stage_3_rag_triggered'):
                    stats['rag_triggered'] += 1

                # Fetch real-time temporal narrative metrics from backend
                try:
                    temporal_metrics_response = await client.get("http://localhost:8001/temporal/metrics", timeout=1.0)
                    temporal_metrics_response.raise_for_status()
                    temporal_metrics = temporal_metrics_response.json()

                    # Update stats with actual Claude API metrics
                    stats['claude_calls'] = temporal_metrics.get('successful_syntheses', 0)
                    stats['fallback_used'] = temporal_metrics.get('fallback_used', 0)
                    stats['scenes_detected'] = temporal_metrics.get('total_requests', 0)

                except Exception as e:
                    # Silently continue if metrics endpoint is unavailable
                    pass

                # Track peak
                if current_metrics['fire'] > stats['peak_fire']:
                    stats['peak_fire'] = current_metrics['fire']

                # Add to history
                history.append({
                    'elapsed': elapsed,
                    'hazard': current_metrics['hazard'],
                    'fire': current_metrics['fire'],
                    'person': current_metrics['person'],
                    'latency': latency
                })

                # Redraw dashboard
                clear_screen()
                draw_header(scenario_name, elapsed, duration, stats['claude_calls'])
                draw_metrics(current_metrics)
                draw_stats(stats)
                draw_history(history)

                # Status bar
                progress = (step + 1) / total_packets
                progress_bar_width = 60
                filled = int(progress * progress_bar_width)
                bar = "█" * filled + "░" * (progress_bar_width - filled)
                print(f"\n{Colors.BLUE}Progress: [{bar}] {progress * 100:.1f}%{Colors.END}")

            except Exception as e:
                stats['total'] += 1
                stats['success_rate'] = (stats['success'] / stats['total']) * 100
                print(f"{Colors.RED}Error: {str(e)[:60]}{Colors.END}")

            await asyncio.sleep(delay)

        # Final summary
        print(f"\n{Colors.GREEN}{Colors.BOLD}{'=' * 80}{Colors.END}")
        print(f"{Colors.GREEN}{Colors.BOLD}STREAM COMPLETE{Colors.END}")
        print(f"{Colors.GREEN}{Colors.BOLD}{'=' * 80}{Colors.END}")
        print(f"Packets Sent:     {stats['total']}")
        print(f"Success Rate:     {stats['success_rate']:.1f}%")
        print(f"Avg Latency:      {stats['avg_latency']:.2f}ms")
        print(f"Peak Fire:        {stats['peak_fire']:.1%}")
        print(f"RAG Triggered:    {stats['rag_triggered']} times")
        if stats['claude_calls'] > 0:
            print(f"{Colors.CYAN}Claude API Calls: {stats['claude_calls']}{Colors.END}")
        print(f"Total Duration:   {elapsed:.1f}s")
        print()


async def main():
    parser = argparse.ArgumentParser(description="Terminal Real-Time RAG Dashboard")
    parser.add_argument(
        "--scenario",
        choices=list(SCENARIOS.keys()),
        default="growing_warehouse_fire",
        help="Scenario to stream"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=None,
        help="Override scenario duration (seconds)"
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=2.0,
        help="Update rate in Hz (default: 2.0)"
    )

    args = parser.parse_args()

    # Show available scenarios
    print(f"\n{Colors.BOLD}Available Scenarios:{Colors.END}")
    for name, scenario in SCENARIOS.items():
        marker = "→" if name == args.scenario else " "
        print(f"  {marker} {Colors.CYAN}{name:30s}{Colors.END} - {scenario['description']}")
    print()

    try:
        await stream_with_dashboard(
            args.scenario,
            args.duration or SCENARIOS[args.scenario]["duration_seconds"],
            args.rate
        )
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}⏹️  Stream stopped by user{Colors.END}\n")


if __name__ == "__main__":
    asyncio.run(main())
