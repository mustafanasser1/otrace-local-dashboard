import type { ReactNode } from "react";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { AnimatedNumber } from "./visuals";

export type Accent = "fl" | "otrace" | "verified" | "neutral";

const accentText: Record<Accent, string> = {
  fl: "text-fl",
  otrace: "text-otrace",
  verified: "text-verified",
  neutral: "text-foreground",
};

const accentSoft: Record<Accent, string> = {
  fl: "bg-fl-soft text-fl border-fl/20",
  otrace: "bg-otrace-soft text-otrace border-otrace/25",
  verified: "bg-verified-soft text-verified border-verified/25",
  neutral: "bg-muted text-muted-foreground border-border",
};

export function PageHeader({
  title,
  subtitle,
  right,
}: {
  title: string;
  subtitle?: string;
  right?: ReactNode;
}) {
  return (
    <header className="mb-7 flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 className="text-[26px] font-semibold tracking-tight text-foreground">{title}</h1>
        {subtitle ? (
          <p className="mt-1.5 max-w-3xl text-[14.5px] leading-relaxed text-muted-foreground">
            {subtitle}
          </p>
        ) : null}
      </div>
      {right}
    </header>
  );
}

export function Panel({
  title,
  description,
  accent = "neutral",
  icon,
  actions,
  children,
  className,
}: {
  title?: string;
  description?: string;
  accent?: Accent;
  icon?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("panel lift overflow-hidden", className)}>
      {title ? (
        <div className="flex items-start justify-between gap-4 border-b border-border px-6 py-4">
          <div className="flex items-start gap-3">
            {icon ? (
              <span
                className={cn(
                  "mt-0.5 flex size-8 items-center justify-center rounded-md border",
                  accentSoft[accent],
                )}
              >
                {icon}
              </span>
            ) : null}
            <div>
              <h2 className="text-[15.5px] font-semibold text-foreground">{title}</h2>
              {description ? (
                <p className="mt-1 max-w-2xl text-[13.5px] leading-relaxed text-muted-foreground">
                  {description}
                </p>
              ) : null}
            </div>
          </div>
          {actions}
        </div>
      ) : null}
      <div className="px-6 py-5">{children}</div>
    </section>
  );
}

export function StatCard({
  label,
  value,
  hint,
  accent = "neutral",
  icon,
}: {
  label: string;
  value: string;
  hint?: string | undefined;
  accent?: Accent;
  icon?: ReactNode;
}) {
  const parsed = /^([^\d-]*)(-?\d+(?:\.\d+)?)(.*)$/.exec(value);

  return (
    <div className="panel lift fade-up px-5 py-4">
      <div className="flex items-center justify-between">
        <span className="text-[12.5px] font-medium uppercase tracking-wide text-muted-foreground">
          {label}
        </span>
        {icon ? <span className={cn("opacity-70", accentText[accent])}>{icon}</span> : null}
      </div>
      <div className={cn("num mt-2 text-[28px] font-semibold leading-none", accentText[accent])}>
        {parsed ? (
          <AnimatedNumber
            value={Number(parsed[2])}
            decimals={(parsed[2]!.split(".")[1] ?? "").length}
            prefix={parsed[1] ?? ""}
            suffix={parsed[3] ?? ""}
          />
        ) : (
          value
        )}
      </div>
      {hint ? <div className="mt-2 text-[12.5px] text-muted-foreground">{hint}</div> : null}
    </div>
  );
}

export function Chip({
  children,
  accent = "neutral",
}: {
  children: ReactNode;
  accent?: Accent;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[12px] font-medium",
        accentSoft[accent],
      )}
    >
      {children}
    </span>
  );
}

export function FlowChain({
  steps,
  accent,
  note,
}: {
  steps: string[];
  accent: Accent;
  note?: string;
}) {
  return (
    <div>
      <ol className="flex flex-wrap items-center gap-2">
        {steps.map((step, i) => (
          <li key={step} className="flex items-center gap-2">
            <span
              className={cn(
                "rounded-md border px-3 py-2 text-[13.5px] font-medium transition-transform hover:-translate-y-0.5",
                accentSoft[accent],
              )}
            >
              {step}
            </span>
            {i < steps.length - 1 ? (
              <ChevronRight className={cn("size-4 shrink-0", accentText[accent])} />
            ) : null}
          </li>
        ))}
      </ol>
      {note ? (
        <p className="mt-4 text-[13.5px] leading-relaxed text-muted-foreground">{note}</p>
      ) : null}
    </div>
  );
}

export function DataRow({
  label,
  value,
  mono,
}: {
  label: string;
  value: ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-6 border-b border-border/70 py-2.5 last:border-0">
      <span className="text-[13.5px] text-muted-foreground">{label}</span>
      <span
        className={cn(
          "text-right text-[14px] font-medium text-foreground",
          mono && "num font-mono text-[13.5px]",
        )}
      >
        {value}
      </span>
    </div>
  );
}