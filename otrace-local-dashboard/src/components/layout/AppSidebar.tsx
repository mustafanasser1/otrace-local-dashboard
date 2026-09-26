import { Link } from "@tanstack/react-router";
import {
  LayoutDashboard,
  FlaskConical,
  Network,
  Route as RouteIcon,
  ShieldCheck,
  ClipboardCheck,
  FileText,
  FolderTree,
  Settings,
} from "lucide-react";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/experiment", label: "Experiment", icon: FlaskConical },
  { to: "/federated-learning", label: "Federated Learning", icon: Network },
  { to: "/otrace", label: "OTrace", icon: RouteIcon },
  { to: "/gdpr", label: "GDPR & Consent", icon: ShieldCheck },
  { to: "/evaluation", label: "Evaluation & Validation", icon: ClipboardCheck },
  { to: "/reports", label: "Reports", icon: FileText },
  { to: "/source-code", label: "Source Code Explorer", icon: FolderTree },
  { to: "/settings", label: "Settings", icon: Settings },
] as const;

export function AppSidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-[270px] flex-col bg-sidebar text-sidebar-foreground lg:flex">
      <div className="border-b border-sidebar-border px-6 py-6">
        <div className="text-[15px] font-semibold tracking-tight text-sidebar-accent-foreground">
          OTrace-FL
        </div>
        <div className="mt-1 text-[12.5px] leading-snug text-sidebar-foreground/70">
          Research Prototype
        </div>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
        {NAV.map(({ to, label, icon: Icon }) => (
          <Link
            key={to}
            to={to}
            activeOptions={{ exact: to === "/" }}
            className="group flex items-center gap-3 rounded-md px-3 py-2.5 text-[14px] font-medium text-sidebar-foreground/80 transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
            activeProps={{
              className:
                "bg-sidebar-accent text-sidebar-accent-foreground shadow-[inset_3px_0_0_0_var(--sidebar-primary)]",
            }}
          >
            <Icon className="size-[18px] shrink-0 opacity-80" strokeWidth={1.9} />
            <span>{label}</span>
          </Link>
        ))}
      </nav>

      <div className="border-t border-sidebar-border px-6 py-5 text-[12px] leading-relaxed text-sidebar-foreground/60">
        PhD research prototype. Supports GDPR-aware traceability and compliance
        validation; it does not certify full GDPR compliance.
      </div>
    </aside>
  );
}

export function MobileNav() {
  return (
    <div className="border-b border-border bg-sidebar px-4 py-3 lg:hidden">
      <div className="mb-3 text-[14px] font-semibold text-sidebar-accent-foreground">
        OTrace-FL Research Prototype
      </div>
      <div className="flex flex-wrap gap-1.5">
        {NAV.map(({ to, label }) => (
          <Link
            key={to}
            to={to}
            activeOptions={{ exact: to === "/" }}
            className="rounded-md px-2.5 py-1.5 text-[12.5px] text-sidebar-foreground/75 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
            activeProps={{ className: "bg-sidebar-accent text-sidebar-accent-foreground" }}
          >
            {label}
          </Link>
        ))}
      </div>
    </div>
  );
}