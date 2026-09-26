import { useEffect, useRef, useState, type ReactNode } from "react";
import { ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Accent } from "./primitives";

/* ------------------------------------------------------------------ *
 * Shared visual primitives: CSS/SVG diagrams and charts.
 * Every chart renders values passed in by the caller — no synthetic
 * series, no interpolated points, no invented data.
 * ------------------------------------------------------------------ */

const stroke: Record<Accent, string> = {
  fl: "stroke-fl",
  otrace: "stroke-otrace",
  verified: "stroke-verified",
  neutral: "stroke-border",
};

const fillSoft: Record<Accent, string> = {
  fl: "fill-fl-soft",
  otrace: "fill-otrace-soft",
  verified: "fill-verified-soft",
  neutral: "fill-muted",
};

const text: Record<Accent, string> = {
  fl: "text-fl",
  otrace: "text-otrace",
  verified: "text-verified",
  neutral: "text-muted-foreground",
};

const bg: Record<Accent, string> = {
  fl: "bg-fl",
  otrace: "bg-otrace",
  verified: "bg-verified",
  neutral: "bg-muted-foreground",
};

const soft: Record<Accent, string> = {
  fl: "bg-fl-soft text-fl border-fl/25",
  otrace: "bg-otrace-soft text-otrace border-otrace/25",
  verified: "bg-verified-soft text-verified border-verified/25",
  neutral: "bg-muted text-muted-foreground border-border",
};

function prefersReducedMotion() {
  if (typeof window === "undefined") return true;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** Counts up to a fixed, verified value once on mount. */
export function AnimatedNumber({
  value,
  decimals = 0,
  prefix = "",
  suffix = "",
  duration = 750,
}: {
  value: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  duration?: number;
}) {
  const [shown, setShown] = useState(value);
  const fromRef = useRef(0);
  const started = useRef(false);

  useEffect(() => {
    const from = started.current ? fromRef.current : 0;
    started.current = true;
    if (prefersReducedMotion()) {
      fromRef.current = value;
      setShown(value);
      return;
    }
    setShown(from);
    const t0 = performance.now();
    let raf = 0;
    const tick = (t: number) => {
      const p = Math.min(1, (t - t0) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      const current = from + (value - from) * eased;
      fromRef.current = current;
      setShown(current);
      if (p < 1) {
        raf = requestAnimationFrame(tick);
      } else {
        fromRef.current = value;
        setShown(value);
      }
    };
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      // Never leave the display stranded mid-animation on an interrupted run.
      fromRef.current = value;
      setShown(value);
    };
  }, [value, duration]);


  return (
    <>
      {prefix}
      {shown.toFixed(decimals)}
      {suffix}
    </>
  );
}

/** Donut / ring progress. Value and max are always displayed literally. */
export function Ring({
  value,
  max,
  accent = "verified",
  size = 132,
  caption,
  centerLabel,
  centerSub,
}: {
  value: number;
  max: number;
  accent?: Accent;
  size?: number;
  caption?: string;
  centerLabel?: string;
  centerSub?: string;
}) {
  const r = 54;
  const c = 2 * Math.PI * r;
  const pct = max > 0 ? Math.min(1, value / max) : 0;
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    const id = requestAnimationFrame(() => setMounted(true));
    return () => cancelAnimationFrame(id);
  }, []);

  return (
    <figure className="flex flex-col items-center">
      <svg width={size} height={size} viewBox="0 0 128 128" role="img" aria-label={caption ?? "progress ring"}>
        <circle cx="64" cy="64" r={r} className="stroke-border" strokeWidth="10" fill="none" />
        <circle
          cx="64"
          cy="64"
          r={r}
          className={cn(stroke[accent], "transition-[stroke-dashoffset] duration-[900ms] ease-out")}
          strokeWidth="10"
          strokeLinecap="round"
          fill="none"
          strokeDasharray={c}
          strokeDashoffset={mounted ? c * (1 - pct) : c}
          transform="rotate(-90 64 64)"
        />
        <text
          x="64"
          y="60"
          textAnchor="middle"
          className={cn("num fill-current text-[21px] font-semibold", text[accent])}
        >
          {centerLabel ?? `${Math.round(pct * 100)}%`}
        </text>
        <text x="64" y="80" textAnchor="middle" className="fill-current text-[12px] text-muted-foreground">
          {centerSub ?? `${value}/${max}`}
        </text>
      </svg>
      {caption ? <figcaption className="mt-2 text-[12.5px] text-muted-foreground">{caption}</figcaption> : null}
    </figure>
  );
}

/** Horizontal metric bar. `max` defaults to 100 for percentage metrics. */
export function MetricBar({
  label,
  value,
  max = 100,
  accent = "verified",
  display,
}: {
  label: string;
  value: number;
  max?: number;
  accent?: Accent;
  display?: string;
}) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    const id = requestAnimationFrame(() => setMounted(true));
    return () => cancelAnimationFrame(id);
  }, []);
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;

  return (
    <div className="py-2">
      <div className="mb-1.5 flex items-baseline justify-between gap-4">
        <span className="text-[13.5px] text-muted-foreground">{label}</span>
        <span className="num text-[14px] font-semibold text-foreground">{display ?? `${value}%`}</span>
      </div>
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={cn("h-full rounded-full transition-[width] duration-[900ms] ease-out", bg[accent])}
          style={{ width: mounted ? `${pct}%` : "0%" }}
        />
      </div>
    </div>
  );
}

/** Two-or-more bar comparison on a shared scale (e.g. runtime seconds). */
export function CompareBars({
  items,
  unit,
  footnote,
}: {
  items: { label: string; value: number; accent: Accent }[];
  unit: string;
  footnote?: ReactNode;
}) {
  const max = Math.max(...items.map((i) => i.value));
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    const id = requestAnimationFrame(() => setMounted(true));
    return () => cancelAnimationFrame(id);
  }, []);

  return (
    <div>
      <div className="space-y-4">
        {items.map((i) => (
          <div key={i.label}>
            <div className="mb-1.5 flex items-baseline justify-between gap-4">
              <span className="text-[13.5px] text-muted-foreground">{i.label}</span>
              <span className="num text-[14px] font-semibold text-foreground">
                {i.value.toFixed(2)} {unit}
              </span>
            </div>
            <div className="h-3.5 w-full overflow-hidden rounded-md bg-muted">
              <div
                className={cn("h-full rounded-md transition-[width] duration-[900ms] ease-out", bg[i.accent])}
                style={{ width: mounted ? `${(i.value / max) * 100}%` : "0%" }}
              />
            </div>
          </div>
        ))}
      </div>
      {footnote ? <div className="mt-4 text-[13px] leading-relaxed text-muted-foreground">{footnote}</div> : null}
    </div>
  );
}

/** Icon pipeline with directional connectors that animate on hover. */
export function IconPipeline({
  nodes,
  accent = "otrace",
  note,
}: {
  nodes: { icon: ReactNode; label: string; sub?: string }[];
  accent?: Accent;
  note?: string;
}) {
  return (
    <div>
      <ol className="group/pipe flex flex-wrap items-stretch gap-2">
        {nodes.map((n, i) => (
          <li key={n.label} className="flex flex-1 items-center gap-2">
            <div
              className={cn(
                "flex min-w-0 flex-1 flex-col items-center gap-2 rounded-md border px-3 py-4 text-center transition-all duration-200 hover:-translate-y-0.5 hover:shadow-raised",
                soft[accent],
              )}
            >
              <span className="flex size-9 items-center justify-center rounded-full border border-border bg-card">
                {n.icon}
              </span>
              <span className="text-[13.5px] font-medium leading-tight">{n.label}</span>
              {n.sub ? <span className="text-[12px] leading-snug text-muted-foreground">{n.sub}</span> : null}
            </div>
            {i < nodes.length - 1 ? (
              <ArrowRight
                className={cn(
                  "size-4 shrink-0 transition-transform duration-200 group-hover/pipe:translate-x-0.5",
                  text[accent],
                )}
              />
            ) : null}
          </li>
        ))}
      </ol>
      {note ? <p className="mt-4 text-[13.5px] leading-relaxed text-muted-foreground">{note}</p> : null}
    </div>
  );
}

/** Round completion markers — presence only, no per-round metrics. */
export function RoundTrack({ rounds, note }: { rounds: number; note?: string }) {
  return (
    <div>
      <div className="flex flex-wrap items-center gap-1.5">
        {Array.from({ length: rounds }, (_, i) => (
          <div key={i} className="flex items-center gap-1.5">
            <span
              className="num flex size-10 items-center justify-center rounded-full border border-fl/30 bg-fl-soft text-[13.5px] font-semibold text-fl transition-transform duration-200 hover:-translate-y-0.5"
              title={`Round ${i + 1} completed`}
            >
              {i + 1}
            </span>
            {i < rounds - 1 ? <span className="h-px w-4 bg-fl/30" /> : null}
          </div>
        ))}
      </div>
      {note ? <p className="mt-3 text-[13px] leading-relaxed text-muted-foreground">{note}</p> : null}
    </div>
  );
}

/** Radar over the five recorded final metrics. */
export function MetricRadar({ metrics }: { metrics: { label: string; value: number }[] }) {
  const cx = 150;
  const cy = 140;
  const R = 92;
  const n = metrics.length;
  const point = (i: number, rad: number) => {
    const a = (Math.PI * 2 * i) / n - Math.PI / 2;
    return [cx + Math.cos(a) * rad, cy + Math.sin(a) * rad] as const;
  };
  const grid = [0.25, 0.5, 0.75, 1];
  const poly = metrics.map((m, i) => point(i, (Math.min(100, m.value) / 100) * R).join(",")).join(" ");

  return (
    <svg viewBox="0 0 300 280" className="w-full" role="img" aria-label="Final metric radar">
      {grid.map((g) => (
        <polygon
          key={g}
          points={metrics.map((_, i) => point(i, R * g).join(",")).join(" ")}
          className="fill-none stroke-border"
          strokeWidth="1"
        />
      ))}
      {metrics.map((m, i) => {
        const [x, y] = point(i, R);
        return <line key={m.label} x1={cx} y1={cy} x2={x} y2={y} className="stroke-border" strokeWidth="1" />;
      })}
      <polygon points={poly} className="fill-fl/20 stroke-fl" strokeWidth="2" />
      {metrics.map((m, i) => {
        const [x, y] = point(i, (Math.min(100, m.value) / 100) * R);
        return <circle key={m.label} cx={x} cy={y} r="3.5" className="fill-fl" />;
      })}
      {metrics.map((m, i) => {
        const [x, y] = point(i, R + 26);
        return (
          <text
            key={m.label}
            x={x}
            y={y}
            textAnchor="middle"
            dominantBaseline="middle"
            className="fill-current text-[11.5px] font-medium text-muted-foreground"
          >
            {m.label} {m.value.toFixed(1)}
          </text>
        );
      })}
    </svg>
  );
}

/** Compact federated topology for the dashboard. */
export function FederatedMiniDiagram({
  clients,
  hospitalsPerClient,
}: {
  clients: number;
  hospitalsPerClient: number;
}) {
  const W = 620;
  const boxW = 168;
  const gap = (W - clients * boxW) / (clients + 1);
  const xs = Array.from({ length: clients }, (_, i) => gap + i * (boxW + gap));

  return (
    <svg viewBox={`0 0 ${W} 250`} className="w-full" role="img" aria-label="Federated topology">
      {/* server */}
      <g>
        <rect x={W / 2 - 118} y="8" width="236" height="60" rx="8" className={cn(fillSoft.fl, "stroke-fl/40")} />
        <text x={W / 2} y="32" textAnchor="middle" className="fill-current text-[13px] font-semibold text-fl">
          Global Model / Server
        </text>
        <text x={W / 2} y="52" textAnchor="middle" className="fill-current text-[11.5px] text-muted-foreground">
          FedAvg · Secure Aggregation
        </text>
      </g>

      {xs.map((x, i) => {
        const midX = x + boxW / 2;
        return (
          <g key={i} className="group">
            <path
              d={`M ${midX} 150 C ${midX} 110, ${W / 2} 110, ${W / 2} 72`}
              className="stroke-fl/60"
              strokeWidth="1.6"
              fill="none"
              strokeDasharray="5 4"
              markerEnd="url(#fl-arrow)"
            />
            <rect x={x} y="150" width={boxW} height="82" rx="8" className="fill-card stroke-border" />
            <text x={midX} y="174" textAnchor="middle" className="fill-current text-[12.5px] font-semibold text-foreground">
              Client Group {i}
            </text>
            <text x={midX} y="194" textAnchor="middle" className="fill-current text-[11.5px] text-muted-foreground">
              {hospitalsPerClient} hospitals
            </text>
            <text x={midX} y="214" textAnchor="middle" className="fill-current text-[11.5px] text-verified">
              raw data stays local
            </text>
          </g>
        );
      })}

      <text x={W / 2} y="112" textAnchor="middle" className="fill-current text-[11.5px] font-medium text-fl">
        model updates only
      </text>

      <defs>
        <marker id="fl-arrow" markerWidth="7" markerHeight="7" refX="5.5" refY="3" orient="auto">
          <path d="M0,0 L6,3 L0,6 z" className="fill-fl" />
        </marker>
      </defs>
    </svg>
  );
}

/** Full federated architecture diagram for the Federated Learning page. */
export function FederatedArchitecture({
  clients,
  hospitalsPerClient,
  hospitals,
  stays,
  rounds,
  localEpochs,
}: {
  clients: number;
  hospitalsPerClient: number;
  hospitals: number;
  stays: number;
  rounds: number;
  localEpochs: number;
}) {
  const W = 960;
  const boxW = 240;
  const leftPad = 20;
  const rightLane = 100;
  const gap = (W - leftPad - rightLane - clients * boxW) / (clients - 1);
  const xs = Array.from({ length: clients }, (_, i) => leftPad + i * (boxW + gap));
  const cx = (W - rightLane + leftPad) / 2;

  return (
    <svg viewBox={`0 0 ${W} 500`} className="w-full" role="img" aria-label="Federated learning architecture">
      <defs>
        <marker id="a-fl" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
          <path d="M0,0 L6,3 L0,6 z" className="fill-fl" />
        </marker>
        <marker id="a-ot" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
          <path d="M0,0 L6,3 L0,6 z" className="fill-otrace" />
        </marker>
      </defs>

      {/* dataset */}
      <rect x={cx - 160} y="6" width="320" height="60" rx="8" className="fill-card stroke-border" />
      <text x={cx} y="30" textAnchor="middle" className="fill-current text-[13.5px] font-semibold text-foreground">
        eICU Collaborative Research Database
      </text>
      <text x={cx} y="50" textAnchor="middle" className="fill-current text-[12px] text-muted-foreground">
        {hospitals} hospitals · {stays.toLocaleString()} ICU stays
      </text>

      {/* dataset -> clients */}
      {xs.map((x, i) => (
        <path
          key={`d${i}`}
          d={`M ${cx} 66 C ${cx} 96, ${x + boxW / 2} 96, ${x + boxW / 2} 120`}
          className="stroke-border"
          strokeWidth="1.6"
          fill="none"
          markerEnd="url(#a-fl)"
        />
      ))}
      <text x={cx + 180} y="92" textAnchor="start" className="fill-current text-[11.5px] text-muted-foreground">
        hospital-level partition
      </text>

      {/* clients */}
      {xs.map((x, i) => (
        <g key={i}>
          <rect x={x} y="120" width={boxW} height="120" rx="8" className={cn(fillSoft.fl, "stroke-fl/35")} />
          <text x={x + boxW / 2} y="146" textAnchor="middle" className="fill-current text-[13px] font-semibold text-fl">
            Client Group {i}
          </text>
          <text x={x + boxW / 2} y="168" textAnchor="middle" className="fill-current text-[12px] text-foreground">
            {hospitalsPerClient} hospitals
          </text>
          <text x={x + boxW / 2} y="188" textAnchor="middle" className="fill-current text-[12px] text-foreground">
            Local training · {localEpochs} epochs
          </text>
          <rect
            x={x + 30}
            y="200"
            width={boxW - 60}
            height="26"
            rx="13"
            className="fill-card stroke-verified/40"
          />
          <text x={x + boxW / 2} y="217" textAnchor="middle" className="fill-current text-[11.5px] font-medium text-verified">
            raw data never leaves
          </text>
        </g>
      ))}

      {/* clients -> aggregation */}
      {xs.map((x, i) => (
        <path
          key={`u${i}`}
          d={`M ${x + boxW / 2} 240 C ${x + boxW / 2} 285, ${cx} 285, ${cx} 316`}
          className="stroke-fl"
          strokeWidth="1.8"
          fill="none"
          strokeDasharray="6 5"
          markerEnd="url(#a-fl)"
        />
      ))}
      <rect x={cx - 168} y="262" width="336" height="24" rx="12" className="fill-card stroke-fl/30" />
      <text x={cx} y="278" textAnchor="middle" className="fill-current text-[12px] font-semibold text-fl">
        masked model updates only — NO RAW DATA
      </text>

      {/* aggregation */}
      <rect x={cx - 220} y="316" width="440" height="58" rx="8" className={cn(fillSoft.otrace, "stroke-otrace/40")} />
      <text x={cx} y="340" textAnchor="middle" className="fill-current text-[13.5px] font-semibold text-otrace">
        Secure Aggregation + FedAvg
      </text>
      <text x={cx} y="360" textAnchor="middle" className="fill-current text-[11.5px] text-muted-foreground">
        server sums masked updates; no single contribution is visible
      </text>

      <path d={`M ${cx} 374 L ${cx} 408`} className="stroke-otrace" strokeWidth="1.8" markerEnd="url(#a-ot)" />

      {/* global model */}
      <rect x={cx - 130} y="410" width="260" height="54" rx="8" className={cn(fillSoft.verified, "stroke-verified/40")} />
      <text x={cx} y="434" textAnchor="middle" className="fill-current text-[13.5px] font-semibold text-verified">
        Global Model
      </text>
      <text x={cx} y="453" textAnchor="middle" className="fill-current text-[11.5px] text-muted-foreground">
        redistributed to every client group
      </text>

      {/* loop back */}
      <path
        d={`M ${cx + 130} 437 C ${W - 30} 437, ${W - 30} 132, ${xs[clients - 1]! + boxW + 6} 150`}
        className="stroke-fl/60"
        strokeWidth="1.6"
        fill="none"
        strokeDasharray="5 5"
        markerEnd="url(#a-fl)"
      />
      <text x={W - 24} y="300" textAnchor="end" className="fill-current text-[12px] font-medium text-fl">
        next round · ×{rounds}
      </text>
    </svg>
  );
}

/** Central concept with satellite cards around it (GDPR articles, MRs). */
export function ConceptOrbit({
  centerTitle,
  centerSub,
  accent = "fl",
  items,
}: {
  centerTitle: string;
  centerSub?: string;
  accent?: Accent;
  items: { key: string; node: ReactNode }[];
}) {
  const half = Math.ceil(items.length / 2);
  const left = items.slice(0, half);
  const right = items.slice(half);

  const column = (list: typeof items, side: "left" | "right") => (
    <div className="flex flex-col gap-3">
      {list.map((it) => (
        <div key={it.key} className="flex items-center gap-2">
          {side === "right" ? <span className="h-px w-4 shrink-0 bg-border" /> : null}
          <div className="flex-1 transition-transform duration-200 hover:-translate-y-0.5">{it.node}</div>
          {side === "left" ? <span className="h-px w-4 shrink-0 bg-border" /> : null}
        </div>
      ))}
    </div>
  );

  return (
    <div className="grid items-center gap-4 lg:grid-cols-[1fr_auto_1fr]">
      {column(left, "left")}
      <div
        className={cn(
          "mx-auto flex size-40 flex-col items-center justify-center rounded-full border-2 px-4 text-center",
          soft[accent],
        )}
      >
        <span className="text-[14px] font-semibold leading-tight">{centerTitle}</span>
        {centerSub ? <span className="mt-1 text-[11.5px] leading-snug text-muted-foreground">{centerSub}</span> : null}
      </div>
      {column(right, "right")}
    </div>
  );
}

/** Small labelled composition tiles (dataset shape, etc.). */
export function CompositionTiles({
  items,
}: {
  items: { icon: ReactNode; value: string; label: string; accent: Accent }[];
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      {items.map((i) => (
        <div
          key={i.label}
          className={cn(
            "flex flex-col items-center rounded-md border px-3 py-4 text-center transition-transform duration-200 hover:-translate-y-0.5",
            soft[i.accent],
          )}
        >
          <span className="mb-1.5">{i.icon}</span>
          <span className="num text-[20px] font-semibold leading-none">{i.value}</span>
          <span className="mt-1.5 text-[12px] text-muted-foreground">{i.label}</span>
        </div>
      ))}
    </div>
  );
}

/** Status rows with icons for on/off settings. */
export function StatusRows({
  rows,
}: {
  rows: { icon: ReactNode; label: string; state: string; accent: Accent; sub?: string }[];
}) {
  return (
    <div className="space-y-2.5">
      {rows.map((r) => (
        <div
          key={r.label}
          className="flex items-center gap-3 rounded-md border border-border bg-secondary/40 px-3.5 py-3 transition-colors hover:bg-accent/60"
        >
          <span className={cn("flex size-8 items-center justify-center rounded-md border", soft[r.accent])}>
            {r.icon}
          </span>
          <div className="min-w-0 flex-1">
            <div className="text-[13.5px] font-medium text-foreground">{r.label}</div>
            {r.sub ? <div className="text-[12px] text-muted-foreground">{r.sub}</div> : null}
          </div>
          <span className={cn("rounded-full border px-2.5 py-0.5 text-[12px] font-semibold", soft[r.accent])}>
            {r.state}
          </span>
        </div>
      ))}
    </div>
  );
}

/** Vertical/step flow with icon nodes, used for erasure and event workflows. */
export function StepFlow({
  steps,
  accent = "otrace",
  note,
}: {
  steps: { icon: ReactNode; title: string; sub?: string }[];
  accent?: Accent;
  note?: string;
}) {
  return (
    <div>
      <ol className="group/flow flex flex-col gap-2 md:flex-row md:items-stretch">
        {steps.map((s, i) => (
          <li key={s.title} className="flex flex-1 items-center gap-2">
            <div
              className={cn(
                "flex min-w-0 flex-1 items-center gap-3 rounded-md border px-3 py-3 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-raised md:flex-col md:items-start",
                soft[accent],
              )}
            >
              <span className="flex size-8 shrink-0 items-center justify-center rounded-md border border-border bg-card">
                {s.icon}
              </span>
              <div className="min-w-0">
                <div className="text-[13px] font-semibold leading-tight">{s.title}</div>
                {s.sub ? <div className="mt-0.5 text-[11.5px] leading-snug text-muted-foreground">{s.sub}</div> : null}
              </div>
            </div>
            {i < steps.length - 1 ? (
              <ArrowRight
                className={cn(
                  "size-4 shrink-0 rotate-90 transition-transform duration-200 md:rotate-0 md:group-hover/flow:translate-x-0.5",
                  text[accent],
                )}
              />
            ) : null}
          </li>
        ))}
      </ol>
      {note ? <p className="mt-4 text-[13.5px] leading-relaxed text-muted-foreground">{note}</p> : null}
    </div>
  );
}