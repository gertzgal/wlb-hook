import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import { readFileSync, statSync } from "node:fs";
import { homedir } from "node:os";
import { resolve } from "node:path";

const DEFAULT_FILE = resolve(homedir(), ".claude/wlb-hook/events.jsonl");
const eventsFile = process.env.WLB_EVENTS_FILE ?? DEFAULT_FILE;

/** Serves the events file at /api/events with its mtime so the page can poll cheaply. */
function eventsApi(): Plugin {
  return {
    name: "wlb-events-api",
    configureServer(server) {
      server.middlewares.use("/api/events", (_req, res) => {
        let text = "";
        let mtime = 0;
        let exists = true;
        try {
          mtime = statSync(eventsFile).mtimeMs;
          text = readFileSync(eventsFile, "utf8");
        } catch {
          exists = false;
        }
        res.setHeader("Content-Type", "application/json");
        res.setHeader("Cache-Control", "no-store");
        res.end(JSON.stringify({ path: eventsFile, exists, mtime, text }));
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), eventsApi()],
  server: { port: 5178, open: false },
});
