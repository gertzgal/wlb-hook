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

export default function App() {
  const src = useEvents();
  const [dragging, setDragging] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const today = useMemo(() => new Date(), [src.updatedAt]);
  const todayIso = isoDate(today);

  const weeks = useMemo(() => buildWeeks(src.events, today), [src.events, today]);
  const stats = useMemo(() => computeStats(weeks, today), [weeks, today]);

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
        <p className="kicker">Your last six weeks with Claude Code</p>
        <p className="range">{range}</p>
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
                <DayCell key={d.date} day={d} todayIso={todayIso} selected={selected === d.date} onSelect={() => setSelected(selected === d.date ? null : d.date)} />
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

function DayCell({ day, todayIso, selected, onSelect }: { day: DaySummary; todayIso: string; selected: boolean; onSelect: () => void }) {
  const d = fromIso(day.date);
  const weekend = isWeekend(d);
  const future = day.date > todayIso;
  const isToday = day.date === todayIso;
  const cls = ["day", day.state, weekend ? "weekend" : "", future ? "future" : "", isToday ? "today" : "", selected ? "selected" : ""].join(" ");
  const title = day.events.length
    ? `${fmtLong(day.date)} — ${STATE_LABEL[day.state]}, ${hours(day.peakHours)}${day.project ? ` in ${day.project}` : ""}${day.excuse ? `\n“${day.excuse}”` : ""}`
    : fmtLong(day.date);
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
    </button>
  );
}
