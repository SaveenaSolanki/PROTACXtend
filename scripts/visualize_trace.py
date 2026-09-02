#!/usr/bin/env python3
"""Feynman-style trace visualizer for ProtacPilot runs."""

import json
import sys
from pathlib import Path

def render_trace(trace_path: str, output_html: str = None):
    """Render a ProtacPilot trace as a Feynman-style diagram."""
    events = []
    with open(trace_path) as f:
        for line in open(trace_path):
            try:
                events.append(json.loads(line))
            except:
                pass
    
    # Build the visual representation
    html = """<!DOCTYPE html>
<html>
<head>
    <title>ProtacPilot Feynman Trace</title>
    <style>
        body { font-family: monospace; background: #1a1a2e; color: #eee; padding: 20px; }
        .event { border-left: 3px solid #00d4aa; margin: 10px 0; padding: 10px; background: #16213e; border-radius: 4px; }
        .event-type { color: #00d4aa; font-weight: bold; }
        .timestamp { color: #888; font-size: 0.8em; }
        .tool { color: #ff6b6b; }
        .result { color: #4ecdc4; }
        .meta { color: #888; font-size: 0.85em; }
        .arrow { color: #00d4aa; margin: 5px 0; font-size: 1.5em; text-align: center; }
        .meta { color: #888; font-size: 0.8em; }
        .error { color: #ff6b6b; }
        .success { color: #4ecdc4; }
    </style>
</head>
<body>
<h1 style="color:#00d4aa;">Feynman Trace: ProtacPilot Run</h1>
"""
    
    for i, event in enumerate(events):
        evt_type = event.get('event', 'unknown')
        ts = event.get('ts', 0)
        elapsed = event.get('elapsed_s', 0)
        
        if evt_type == 'run_start':
            html += f'<div class="event"><div class="event-type">▶ RUN START</div><div class="meta">{event.get("run_id")} | {event.get("meta",{}).get("mode","?")} | {event.get("meta",{}).get("request","")[:80]}</div>'
        elif evt_type == 'tool_call':
            tool = event.get('tool', 'unknown')
            args = event.get('args', {})
            html += f'<div class="event"><div class="event-type">🔧 TOOL: {tool}</div>'
            if 'args' in event:
                html += f'<div class="meta">args: {str(args)[:100]}...</div>'
            result = event.get('result_summary', {})
            if result:
                html += f'<div class="result">→ {result.get("status","?")} | decisions: {result.get("n_decisions","?")}</div>'
        elif evt_type == 'run_end':
            status = event.get('status', '?')
            color = 'success' if status == 'ok' else 'error' if status == 'failed' else 'warning' if status == 'needs_human' else ''
            html += f'<div class="event"><div class="event-type {color}">■ RUN END: {status.upper()}</div>'
            html += f'<div class="meta">elapsed: {event.get("elapsed_s",0):.1f}s | {event.get("summary",{})}</div>'
        else:
            html += f'<div class="event"><div class="event-type">{evt_type}</div><div class="meta">{json.dumps(event, indent=2)[:200]}</div>'
        
        if i < len(events) - 1:
            html += '<div class="arrow">⬇</div>'
    
    html += "</body></html>"
    
    if output_html:
        Path(output_html).write_text(html)
        print(f"Written to {output_html}")
    else:
        print(html)

if __name__ == "__main__":
    import sys
    import json
    if len(sys.argv) > 1:
        render_trace(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    else:
        print("Usage: python visualize_trace.py <trace.jsonl> [output.html]")

