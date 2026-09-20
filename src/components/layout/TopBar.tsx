import { useEffect, useState } from "react";
import { CircleDot, CloudOff, Wifi } from "lucide-react";
import { useSummary } from "@/hooks/useSummary";

export function TopBar() {
  const { isLive, systemStatus } = useSummary();

  const [now, setNow] = useState<string | null>(null);

  useEffect(() => {
    const tick = () =>
      setNow(
        new Date().toLocaleString(undefined, {
          weekday: "short",
          day: "2-digit",
          month: "short",
          year: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        }),
      );
    tick();
    const id = window.setInterval(tick, 30_000);
    return () => window.clearInterval(id);
  }, []);

  return (
    <div className="sticky top-0 z-20 flex flex-wrap items-center justify-between gap-4 border-b border-border bg-surface/95 px-6 py-3.5 backdrop-blur lg:px-10">
      <div className="min-w-0">
        <div className="truncate text-[14.5px] font-semibold text-foreground">
          OTrace-FL Research Prototype
        </div>
        <div className="truncate text-[12.5px] text-muted-foreground">
          GDPR-aware traceability for distributed AI · data source:{" "}
          {isLive ? "FastAPI backend" : "verified recorded run (offline)"}
        </div>
      </div>

      <div className="flex items-center gap-4">
        <span
          className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[12.5px] font-medium ${
            isLive
              ? "border-verified/25 bg-verified-soft text-verified"
              : "border-otrace/25 bg-otrace-soft text-otrace"
          }`}
          title={isLive ? "GET /ui/api/summary succeeded" : "GET /ui/api/summary failed — using verified fallback data"}
        >
          {isLive ? <Wifi className="size-3.5" /> : <CloudOff className="size-3.5" />}
          {isLive ? "Live Backend" : "Verified Fallback"}
        </span>
        <span
          className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[12.5px] font-medium ${
            isLive
              ? "border-verified/25 bg-verified-soft text-verified"
              : "border-border bg-secondary text-muted-foreground"
          }`}
        >
          <CircleDot className="size-3.5" />
          {systemStatus}
        </span>
        <span className="num hidden text-[13px] text-muted-foreground sm:inline">
          {now ?? "—"}
        </span>

        <span className="flex size-9 items-center justify-center rounded-full bg-primary text-[13px] font-semibold text-primary-foreground">
          MN
        </span>
      </div>
    </div>
  );
}