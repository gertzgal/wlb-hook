export type Kind = "gate" | "stop" | "one_last" | "workaholic";

export interface WlbEvent {
  ts: string;
  date: string;
  kind: Kind;
  worked_hours: number;
  budget_hours: number;
  excuse?: string;
  session_id: string;
  cwd: string;
}

/** Final Day state as the glossary names it, plus two derived cases for the calendar. */
export type DayState = "quiet" | "stopped" | "unlocked" | "one_last" | "ignored";

export interface DaySummary {
  date: string; // YYYY-MM-DD
  state: DayState;
  events: WlbEvent[];
  peakHours: number;
  budget: number;
  excuse?: string;
  excuseTime?: string;
  project?: string;
  gates: number;
  choices: { stop: number; one_last: number; workaholic: number };
}

export function parseEvents(text: string): WlbEvent[] {
  const out: WlbEvent[] = [];
  for (const line of text.split("\n")) {
    const t = line.trim();
    if (!t) continue;
    try {
      const e = JSON.parse(t) as WlbEvent;
      if (e && typeof e.date === "string" && typeof e.kind === "string") out.push(e);
    } catch {
      /* skip bad line */
    }
  }
  return out.sort((a, b) => a.ts.localeCompare(b.ts));
}

export function isoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function fromIso(s: string): Date {
  const [y, m, d] = s.split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function addDays(d: Date, n: number): Date {
  const c = new Date(d);
  c.setDate(c.getDate() + n);
  return c;
}

export function isWeekend(d: Date): boolean {
  const w = d.getDay();
  return w === 0 || w === 6;
}

export function summarizeDay(date: string, events: WlbEvent[]): DaySummary {
  const choices = { stop: 0, one_last: 0, workaholic: 0 };
  let gates = 0;
  let peak = 0;
  let budget = 9;
  let excuse: string | undefined;
  let excuseTime: string | undefined;
  let project: string | undefined;
  for (const e of events) {
    peak = Math.max(peak, e.worked_hours ?? 0);
    if (e.budget_hours) budget = e.budget_hours;
    if (e.cwd) project = e.cwd.split("/").filter(Boolean).pop();
    if (e.kind === "gate") gates++;
    else choices[e.kind]++;
    if (e.kind === "workaholic" && e.excuse) {
      excuse = e.excuse;
      excuseTime = e.ts;
    }
  }
  let state: DayState = "quiet";
  if (events.length) {
    if (choices.workaholic) state = "unlocked";
    else if (choices.stop) state = "stopped";
    else if (choices.one_last) state = "one_last";
    else state = "ignored";
  }
  return { date, state, events, peakHours: peak, budget, excuse, excuseTime, project, gates, choices };
}

export interface Week {
  days: DaySummary[]; // Monday..Sunday
}

/** Six week rows (Mon–Sun) ending on the week that contains `today`. */
export function buildWeeks(events: WlbEvent[], today: Date, weeks = 6): Week[] {
  const byDate = new Map<string, WlbEvent[]>();
  for (const e of events) {
    const arr = byDate.get(e.date) ?? [];
    arr.push(e);
    byDate.set(e.date, arr);
  }
  const dow = (today.getDay() + 6) % 7; // Monday = 0
  const thisMonday = addDays(today, -dow);
  const start = addDays(thisMonday, -7 * (weeks - 1));
  const out: Week[] = [];
  for (let w = 0; w < weeks; w++) {
    const days: DaySummary[] = [];
    for (let i = 0; i < 7; i++) {
      const d = addDays(start, w * 7 + i);
      const iso = isoDate(d);
      days.push(summarizeDay(iso, byDate.get(iso) ?? []));
    }
    out.push({ days });
  }
  return out;
}

export interface Stats {
  streakDays: number; // consecutive weekdays within budget, ending today
  overworkDays: number;
  totalWorkDays: number;
  choices: { stop: number; one_last: number; workaholic: number };
  ignored: number;
  topExcuse?: { text: string; count: number; date: string };
  excuses: { text: string; date: string; ts: string; hours: number }[];
}

export function computeStats(weeks: Week[], today: Date): Stats {
  const all = weeks.flatMap((w) => w.days);
  const todayIso = isoDate(today);
  const past = all.filter((d) => d.date <= todayIso);
  const choices = { stop: 0, one_last: 0, workaholic: 0 };
  let ignored = 0;
  let overwork = 0;
  const counts = new Map<string, { count: number; date: string }>();
  const excuses: Stats["excuses"] = [];
  for (const d of past) {
    choices.stop += d.choices.stop;
    choices.one_last += d.choices.one_last;
    choices.workaholic += d.choices.workaholic;
    if (d.state === "ignored") ignored++;
    if (d.state !== "quiet") overwork++;
    for (const e of d.events) {
      if (e.kind === "workaholic" && e.excuse) {
        const c = counts.get(e.excuse) ?? { count: 0, date: e.date };
        c.count++;
        c.date = e.date;
        counts.set(e.excuse, c);
        excuses.push({ text: e.excuse, date: e.date, ts: e.ts, hours: e.worked_hours });
      }
    }
  }
  let streak = 0;
  for (let i = past.length - 1; i >= 0; i--) {
    const d = past[i];
    if (isWeekend(fromIso(d.date))) continue;
    if (d.state !== "quiet") break;
    streak++;
  }
  let top: Stats["topExcuse"];
  for (const [text, c] of counts) {
    if (!top || c.count > top.count || (c.count === top.count && c.date > top.date)) top = { text, ...c };
  }
  const weekdays = past.filter((d) => !isWeekend(fromIso(d.date))).length;
  return { streakDays: streak, overworkDays: overwork, totalWorkDays: weekdays, choices, ignored, topExcuse: top, excuses };
}
