import type { ReactNode } from "react";
import { DropletsIcon } from "./icons";

export type AppTab = "operations" | "network" | "incidents";

const TABS: { id: AppTab; label: string }[] = [
  { id: "operations", label: "Operations" },
  { id: "network", label: "Water Network" },
  { id: "incidents", label: "Incidents" },
];

interface AppShellProps {
  activeTab: AppTab;
  onNavigate: (tab: AppTab) => void;
  footer: ReactNode;
  children: ReactNode;
}

export function AppShell({ activeTab, onNavigate, footer, children }: AppShellProps) {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-20 border-b border-border/60 bg-background/85 backdrop-blur-lg">
        <div className="mx-auto max-w-6xl px-4 py-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <span className="flex size-9 items-center justify-center rounded-md border border-primary/40 bg-primary/15 text-primary">
                <DropletsIcon className="size-5" />
              </span>
              <div>
                <p className="font-mono text-sm font-semibold tracking-widest text-foreground">
                  NEER
                </p>
                <p className="text-xs text-muted-foreground">
                  Water Intelligence &amp; Response Platform
                </p>
              </div>
            </div>
            <span className="chip bg-warn/15 text-warn border-warn/40">
              <span aria-hidden="true" className="size-1.5 rounded-full bg-current" />
              Demo / Simulation Mode
            </span>
          </div>
          <nav className="mt-3 flex items-center gap-1" aria-label="Primary">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => onNavigate(tab.id)}
                aria-current={activeTab === tab.id ? "page" : undefined}
                className={`rounded-md px-3 py-1.5 text-sm transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                  activeTab === tab.id
                    ? "bg-secondary text-foreground"
                    : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">{children}</main>

      <footer className="border-t border-border/60 py-4">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4">
          <p className="text-xs text-muted-foreground">
            Decision support only — this system never controls water
            infrastructure.
          </p>
          {footer}
        </div>
      </footer>
    </div>
  );
}