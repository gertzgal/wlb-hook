import { useEffect, useMemo, useState } from "react";
import { buildWeeks, computeStats, fromIso, isoDate, isWeekend, type DaySummary } from "./model";
import { useEvents } from "./useEvents";

const MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"];
const DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function fmtTime(ts: string): string {
  const d = new Date(ts);
  return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}
function fmtLong(iso: string): string {
  const d = fromIso(iso);
  return d.toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" });
}
function hours(h: number): string {
  return `${h.toFixed(1).replace(/\.0$/, "")} h`;
}

const STATE_LABEL: Record<DaySummary["state"], string> = {
  quiet: "within budget",
  stopped: "stopped",
  unlocked: "workaholic",
  one_last: "one last prompt",
  ignored: "ignored the gate",
};

const LIMIT_KEY = "wlb.screenTimeLimitHours";
const DEFAULT_LIMIT = 4;

/** Screen-time limit for Claude per day, like Apple's per-app limit. Stored in the browser. */
function useScreenTimeLimit(): [number, (h: number) => void] {
  const [limit, setLimit] = useState<number>(() => {
    const v = Number(localStorage.getItem(LIMIT_KEY));
    return v > 0 ? v : DEFAULT_LIMIT;
  });
  const set = (h: number) => {
    const v = Math.min(12, Math.max(0.5, h));
    setLimit(v);
    localStorage.setItem(LIMIT_KEY, String(v));
  };
  return [limit, set];
}

export default function App() {
  const src = useEvents();
  const [limit, setLimit] = useScreenTimeLimit();
  const [dragging, setDragging] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const today = useMemo(() => new Date(), [src.updatedAt]);
  const todayIso = isoDate(today);

  const weeks = useMemo(() => buildWeeks(src.events, today), [src.events, today]);
  const stats = useMemo(() => {
    const base = computeStats(weeks, today);
    const overLimitDays = weeks.flatMap((w) => w.days).filter((d) => d.date <= todayIso && d.usageHours > limit).length;
    return { ...base, overLimitDays };
  }, [weeks, today, limit, todayIso]);

  const longest = useMemo(() => {
    let best: DaySummary | undefined;
    for (const d of weeks.flatMap((w) => w.days)) if (d.events.length && (!best || d.peakHours > best.peakHours)) best = d;
    return best;
  }, [weeks]);

  const hero = useMemo(() => {
    const ex = stats.excuses;
    if (!ex.length) return undefined;
    return ex[ex.length - 1];
  }, [stats]);

  useEffect(() => {
    const prevent = (e: DragEvent) => e.preventDefault();
    window.addEventListener("dragover", prevent);
    window.addEventListener("drop", prevent);
    return () => {
      window.removeEventListener("dragover", prevent);
      window.removeEventListener("drop", prevent);
    };
  }, []);

  const onDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (!f) return;
    src.loadText(await f.text(), f.name);
  };

  const first = weeks[0].days[0].date;
  const last = weeks[weeks.length - 1].days[6].date;
  const fd = fromIso(first), ld = fromIso(last);
  const range = fd.getMonth() === ld.getMonth()
    ? `${MONTHS[fd.getMonth()]} ${fd.getDate()}–${ld.getDate()}`
    : `${MONTHS[fd.getMonth()]} ${fd.getDate()} – ${MONTHS[ld.getMonth()]} ${ld.getDate()}`;

  const sel = selected ? weeks.flatMap((w) => w.days).find((d) => d.date === selected) : undefined;

  return (
    <div
      className={"page" + (dragging ? " dragging" : "")}
      onDragEnter={() => setDragging(true)}
      onDragLeave={(e) => { if (e.currentTarget === e.target) setDragging(false); }}
      onDrop={onDrop}
    >
      <header className="masthead">
        <div>
          <p className="kicker">Your last six weeks with Claude Code</p>
          <p className="range">{range}</p>
        </div>
        <div className="screentime">
          <p className="st-big">
            {stats.usageDays ? hours(stats.avgUsageHours) : "—"}
            <span className="st-sub"> / day</span>
          </p>
          <p className="stat-label">average time in Claude{stats.usageDays ? `, over ${stats.usageDays} days` : ""}</p>
          <label className="st-limit">
            <span>Daily limit</span>
            <input type="range" min={0.5} max={12} step={0.5} value={limit} onChange={(e) => setLimit(Number(e.target.value))} />
            <b>{hours(limit)}</b>
          </label>
          <p className={"st-verdict " + (stats.avgUsageHours > limit ? "over" : "under")}>
            {stats.usageDays === 0 ? "no usage recorded yet" : Math.abs(stats.avgUsageHours - limit) < 0.05 ? "right at your limit on average" : stats.avgUsageHours > limit ? `${hours(stats.avgUsageHours - limit)} over your limit on average` : `${hours(limit - stats.avgUsageHours)} under your limit on average`}
            {stats.overLimitDays > 0 && ` · ${stats.overLimitDays} ${stats.overLimitDays === 1 ? "day" : "days"} over`}
          </p>
        </div>
      </header>

      {hero && (
        <section className="hero">
          <p className="hero-lead">Latest thing you told the gate</p>
          <blockquote className="hero-quote">
            <span className="mark">“</span>{hero.text}<span className="mark">”</span>
          </blockquote>
          <p className="hero-meta">
            {fmtLong(hero.date)}, {fmtTime(hero.ts)}, {hours(hero.hours)} into the day
          </p>
        </section>
      )}

      <section className="stats">
        <Stat big={String(stats.streakDays)} label={stats.streakDays === 1 ? "workday within budget in a row" : "workdays within budget in a row"} />
        <Stat big={`${stats.overworkDays}`} sub={`of ${stats.totalWorkDays}`} label="workdays past the budget" />
        <div className="stat behavior">
          <p className="stat-label">How you answer the gate</p>
          <ul className="strip">
            <li><i className="sw stopped" />Stop <b>{stats.choices.stop}</b></li>
            <li><i className="sw one_last" />One last <b>{stats.choices.one_last}</b></li>
            <li><i className="sw unlocked" />Workaholic <b>{stats.choices.workaholic}</b></li>
            {stats.ignored > 0 && <li><i className="sw ignored" />Ignored <b>{stats.ignored}</b></li>}
          </ul>
        </div>
        {stats.topExcuse && stats.topExcuse.count > 1 ? (
          <div className="stat top">
            <p className="stat-label">Your go-to excuse, used {stats.topExcuse.count} times</p>
            <p className="stat-quote">“{stats.topExcuse.text}”</p>
          </div>
        ) : longest ? (
          <div className="stat top">
            <p className="stat-label">Longest day on the record</p>
            <p className="stat-quote">{hours(longest.peakHours)} on {fmtLong(longest.date)}{longest.project ? `, in ${longest.project}` : ""}</p>
          </div>
        ) : (
          <div className="stat top">
            <p className="stat-label">Excuses on record</p>
            <p className="stat-quote">None yet. Keep it that way.</p>
          </div>
        )}
      </section>

      <section className="calendar" aria-label="Calendar of the last six weeks">
        <div className="dow-row">
          <span className="month-gutter" />
          {DOW.map((d) => <span key={d} className="dow">{d}</span>)}
        </div>
        {weeks.map((w, wi) => {
          const monthStart = w.days.find((d) => fromIso(d.date).getDate() === 1);
          const label = wi === 0 ? MONTHS[fromIso(w.days[0].date).getMonth()].slice(0, 3) : monthStart ? MONTHS[fromIso(monthStart.date).getMonth()].slice(0, 3) : "";
          return (
            <div className="week" key={w.days[0].date}>
              <span className="month-gutter">{label}</span>
              {w.days.map((d) => (
                <DayCell key={d.date} day={d} todayIso={todayIso} limit={limit} selected={selected === d.date} onSelect={() => setSelected(selected === d.date ? null : d.date)} />
              ))}
            </div>
          );
        })}
      </section>

      {sel && sel.events.length > 0 && (
        <section className="detail">
          <div className="detail-head">
            <h2>{fmtLong(sel.date)}</h2>
            <span className={"pill " + sel.state}>{STATE_LABEL[sel.state]}</span>
            <span className="muted">{hours(sel.peakHours)} of a {sel.budget} h budget{sel.project ? `, in ${sel.project}` : ""}</span>
            {sel.usageHours > 0 && <span className={"muted usage-pill" + (sel.usageHours > limit ? " over" : "")}>{hours(sel.usageHours)} in Claude{sel.usageHours > limit ? `, ${hours(sel.usageHours - limit)} over the ${hours(limit)} limit` : ""}</span>}
            <button className="close" onClick={() => setSelected(null)} aria-label="Close">×</button>
          </div>
          <ol className="timeline">
            {sel.events.filter((e) => e.kind !== "gate").map((e, i) => (
              <li key={i}>
                <span className="t">{fmtTime(e.ts)}</span>
                <i className={"sw " + kindClass(e.kind)} />
                <span>
                  <span className="what">{kindLabel(e.kind)}</span>
                  {e.excuse && <q className="ex">{e.excuse}</q>}
                </span>
              </li>
            ))}
            {sel.events.filter((e) => e.kind === "gate").length > sel.events.filter((e) => e.kind !== "gate").length && (
              <li><span className="t" /><i className="sw ignored" /><span className="what">a gate went unanswered</span></li>
            )}
          </ol>
        </section>
      )}

      <footer className="foot">
        {!src.exists && <p className="warn">No events file at {shortPath(src.label)} yet. The first gate will create it.</p>}
        <p>Quiet days mean you stayed within budget, or didn't open Claude at all. Drop any <code>events.jsonl</code> onto the page to read a different record.</p>
      </footer>

      {dragging && <div className="drop-hint">Drop the events file</div>}
    </div>
  );
}

function kindClass(k: string) {
  return k === "stop" ? "stopped" : k === "workaholic" ? "unlocked" : k === "one_last" ? "one_last" : "ignored";
}
function kindLabel(k: string) {
  return k === "stop" ? "Stopped for the day" : k === "workaholic" ? "Unlocked the day" : k === "one_last" ? "One last prompt" : "Gate";
}

function shortPath(p: string) {
  return p.replace(/^\/Users\/[^/]+/, "~");
}

function Stat({ big, sub, label }: { big: string; sub?: string; label: string }) {
  return (
    <div className="stat">
      <p className="stat-big">{big}{sub && <span className="stat-sub"> {sub}</span>}</p>
      <p className="stat-label">{label}</p>
    </div>
  );
}

function DayCell({ day, todayIso, limit, selected, onSelect }: { day: DaySummary; todayIso: string; limit: number; selected: boolean; onSelect: () => void }) {
  const d = fromIso(day.date);
  const weekend = isWeekend(d);
  const future = day.date > todayIso;
  const isToday = day.date === todayIso;
  const over = day.usageHours > limit;
  const cls = ["day", day.state, weekend ? "weekend" : "", future ? "future" : "", isToday ? "today" : "", selected ? "selected" : "", over ? "over-limit" : ""].join(" ");
  const usageLine = day.usageHours > 0 ? `\n${hours(day.usageHours)} in Claude${over ? ` (over the ${hours(limit)} limit)` : ""}` : "";
  const title = day.events.length
    ? `${fmtLong(day.date)} — ${STATE_LABEL[day.state]}, ${hours(day.peakHours)}${day.project ? ` in ${day.project}` : ""}${day.excuse ? `\n“${day.excuse}”` : ""}${usageLine}`
    : fmtLong(day.date) + usageLine;
  const interactive = day.events.length > 0;
  return (
    <button className={cls} title={title} onClick={interactive ? onSelect : undefined} tabIndex={interactive ? 0 : -1} aria-pressed={selected}>
      <span className="num">{d.getDate()}</span>
      {day.state !== "quiet" && (
        <span className="hrs">{hours(day.peakHours)}</span>
      )}
      {day.excuse ? (
        <span className="excuse">{day.excuse}</span>
      ) : day.state === "stopped" ? (
        <span className="note">closed the laptop{day.choices.stop > 1 ? ` after ${day.choices.stop} tries` : ""}</span>
      ) : day.state === "one_last" ? (
        <span className="note">one last prompt</span>
      ) : day.state === "ignored" ? (
        <span className="note">gate left open</span>
      ) : null}
      {day.usageHours > 0 && (
        <span className="usage" title={`${hours(day.usageHours)} in Claude`}>
          <span className="usage-bar"><span className="usage-fill" style={{ width: `${Math.min(100, (day.usageHours / Math.max(limit, 0.5)) * 100)}%` }} /></span>
          <span className="usage-txt">{hours(day.usageHours)}</span>
        </span>
      )}
    </button>
  );
}
