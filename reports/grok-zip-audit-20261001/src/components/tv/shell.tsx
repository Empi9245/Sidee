import { Button } from "@/components/ui/button";
import { copy } from "@/lib/vidaa/i18n";
import { useAppStore } from "@/lib/vidaa/store";
import { cn } from "@/lib/utils";
import { ArrowLeft, Languages } from "lucide-react";
import type { ReactNode } from "react";

export function Shell({
  children,
  subtitle,
}: {
  children: ReactNode;
  subtitle?: string;
}) {
  const lang = useAppStore((s) => s.lang);
  const view = useAppStore((s) => s.view);
  const fhd = useAppStore((s) => s.fhd);
  const snapshot = useAppStore((s) => s.snapshot);
  const setLang = useAppStore((s) => s.setLang);
  const setView = useAppStore((s) => s.setView);
  const setFhd = useAppStore((s) => s.setFhd);
  const t = copy[lang];
  const real = snapshot?.accessMode === "real-tv";

  return (
    <div className="min-h-dvh bg-bg text-fg">
      <div
        className={cn(
          "px-5 py-3 text-sm border-b border-border",
          real ? "bg-raised text-fg" : "bg-warn/15 text-warn",
        )}
      >
        {real ? t.tvBanner : t.previewBanner}
      </div>
      <header className="flex flex-wrap items-center gap-3 px-5 py-4 border-b border-border">
        {view !== "home" ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setView("home")}
            aria-label={t.back}
          >
            <ArrowLeft className="size-4" />
            {t.back}
          </Button>
        ) : null}
        <div className="flex items-baseline gap-3 min-w-0">
          <p className="font-display text-xl tracking-tight text-fg">
            {t.brand}
            <span className="text-muted"> · </span>
            {t.product}
          </p>
          {subtitle ? (
            <p className="text-sm text-muted truncate hidden sm:block">{subtitle}</p>
          ) : null}
        </div>
        <div className="ml-auto flex items-center gap-2">
          <Button
            variant={fhd ? "primary" : "secondary"}
            size="sm"
            onClick={() => setFhd(!fhd)}
            aria-pressed={fhd}
          >
            {t.fhd}
            <span className="text-xs opacity-80">{fhd ? "hisense" : "store"}</span>
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setLang(lang === "it" ? "en" : "it")}
          >
            <Languages className="size-4" />
            {t.lang}
          </Button>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl px-5 py-6 pb-16">{children}</main>
    </div>
  );
}
