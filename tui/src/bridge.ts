/**
 * PROTACXtend Bridge — JSONL subprocess communication with Python backend.
 *
 * Spawns `python -m synglue_agent.tui_bridge.server` as a child process
 * and communicates via JSON Lines over stdin/stdout.
 */

import { spawn, type ChildProcess } from "node:child_process";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { createInterface, type Interface } from "node:readline";
import { EventEmitter } from "node:events";

const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = resolve(__dirname, "..", "..");

// ── Event types ──────────────────────────────────────────────────

export interface BridgeEvent {
  type: string;
  ts?: number;
  [key: string]: unknown;
}

// ── Bridge class ─────────────────────────────────────────────────

export class PythonBridge extends EventEmitter {
  private process: ChildProcess | null = null;
  private reader: Interface | null = null;
  private ready = false;
  private pendingReady: (() => void)[] = [];

  /** Spawn the Python backend */
  start(): Promise<void> {
    return new Promise((resolveReady, reject) => {
      const python = process.env.PROTACXTEND_PYTHON ?? "python3";
      const args = ["-m", "synglue_agent.tui_bridge.server"];

      this.process = spawn(python, args, {
        cwd: PROJECT_ROOT,
        stdio: ["pipe", "pipe", "pipe"],
        env: { ...process.env, PYTHONUNBUFFERED: "1" },
      });

      this.process.on("error", (err) => {
        this.emit("error", err);
        reject(err);
      });

      this.process.on("exit", (code) => {
        this.emit("exit", code);
        this.ready = false;
      });

      // Read stderr for diagnostics
      this.process.stderr?.on("data", (data: Buffer) => {
        const msg = data.toString().trim();
        if (msg) this.emit("stderr", msg);
      });

      // Read stdout as JSONL
      this.reader = createInterface({ input: this.process.stdout! });
      this.reader.on("line", (line: string) => {
        if (!line.trim()) return;
        try {
          const event: BridgeEvent = JSON.parse(line);
          if (event.type === "ready") {
            this.ready = true;
            for (const fn of this.pendingReady) fn();
            this.pendingReady = [];
          }
          this.emit("event", event);
          this.emit(event.type, event);
        } catch {
          this.emit("parse_error", line);
        }
      });

      // Wait for ready event
      this.pendingReady.push(() => resolveReady());
      // Timeout if backend doesn't start
      setTimeout(() => {
        if (!this.ready) {
          reject(new Error("Python backend did not become ready within 10s"));
        }
      }, 10_000);
    });
  }

  /** Send a command to the Python backend */
  send(type: string, args: Record<string, unknown> = {}): void {
    if (!this.process?.stdin?.writable) {
      throw new Error("Bridge not connected");
    }
    const msg = JSON.stringify({ type, ...args }) + "\n";
    this.process.stdin.write(msg);
  }

  /** Wait for the bridge to be ready */
  whenReady(): Promise<void> {
    if (this.ready) return Promise.resolve();
    return new Promise((resolve) => this.pendingReady.push(resolve));
  }

  /** Gracefully shut down */
  stop(): void {
    if (this.process) {
      this.process.stdin?.end();
      this.process.kill("SIGTERM");
      this.process = null;
    }
    this.ready = false;
  }

  isReady(): boolean {
    return this.ready;
  }
}
