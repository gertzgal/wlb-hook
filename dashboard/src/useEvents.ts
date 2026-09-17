import { useCallback, useEffect, useRef, useState } from "react";
import { parseEvents, type WlbEvent } from "./model";

export interface Source {
  label: string;
  events: WlbEvent[];
  exists: boolean;
  live: boolean;
  updatedAt?: number;
}

/** Polls /api/events every 2 s; a dropped file replaces the source until the file changes on disk again. */
export function useEvents(): Source & { loadText: (text: string, label: string) => void } {
  const [src, setSrc] = useState<Source>({ label: "loading…", events: [], exists: true, live: true });
  const lastMtime = useRef<number>(-1);
  const dropped = useRef(false);

  const loadText = useCallback((text: string, label: string) => {
    dropped.current = true;
    setSrc({ label, events: parseEvents(text), exists: true, live: false, updatedAt: Date.now() });
  }, []);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const r = await fetch("/api/events");
        const j = (await r.json()) as { path: string; exists: boolean; mtime: number; text: string };
        if (!alive) return;
        if (j.mtime !== lastMtime.current) {
          const first = lastMtime.current === -1;
          lastMtime.current = j.mtime;
          if (first || !dropped.current) {
            dropped.current = false;
            setSrc({ label: j.path, events: parseEvents(j.text), exists: j.exists, live: true, updatedAt: Date.now() });
          }
        }
      } catch {
        /* server gone; keep what we have */
      }
    };
    tick();
    const id = setInterval(tick, 2000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  return { ...src, loadText };
}
