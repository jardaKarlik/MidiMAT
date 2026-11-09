import type { ReactNode } from "react";
import { AppSidebar } from "./app-sidebar";

interface AppShellProps {
  title: string;
  subtitle: string;
  children: ReactNode;
}

/**
 * Layout shell, ported from the design's app-shell.tsx. The only change is
 * `min-h-screen` → `h-screen`: inside a fixed WebView2 window the sidebar and
 * the scrollable <main> must be bounded, so the content area owns the scroll.
 */
export function AppShell({ title, subtitle, children }: AppShellProps) {
  return (
    <div className="flex h-screen bg-background">
      <AppSidebar />
      <main className="min-w-0 flex-1 overflow-y-auto px-10 py-8">
        <div className="mx-auto max-w-[880px]">
          <header className="mb-8">
            <h1 className="text-3xl font-semibold tracking-tight">{title}</h1>
            <p className="mt-2 text-sm text-muted-foreground">{subtitle}</p>
          </header>
          {children}
        </div>
      </main>
    </div>
  );
}
