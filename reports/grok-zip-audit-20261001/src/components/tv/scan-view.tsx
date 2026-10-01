import { Button } from "@/components/ui/button";
import { copy } from "@/lib/vidaa/i18n";
import { takeSnapshot } from "@/lib/vidaa/bridge";
import { useAppStore } from "@/lib/vidaa/store";
import { cn } from "@/lib/utils";
import { Radar, Tv } from "lucide-react";

function Pill({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-3 py-1 text-xs border",
        ok
          ? "border-ok/40 bg-ok/10 text-ok"
          : "border-border bg-raised text-muted",
      )}
    >
      {label}
    </span>
  );
}

export function ScanView() {
  const lang = useAppStore((s) => s.lang);
  const snapshot = useAppStore((s) => s.snapshot);
  const setSnapshot = useAppStore((s) => s.setSnapshot);
  const setView = useAppStore((s) => s.setView);
  const t = copy[lang];

  if (!snapshot) {
    return (
      <div className="rounded-[var(--radius-xl)] bg-surface border border-border p-8">
        <p>{t.scanning}</p>
        <Button className="mt-6" variant="primary" onClick={() => setSnapshot(takeSnapshot())}>
          <Radar className="size-5" />
          {t.scan}
        </Button>
      </div>
    );
  }

  const api = snapshot.apis;
  const identityLabel =
    snapshot.identity.assessment === "IDENTITY PRESENT"
      ? t.present
      : snapshot.identity.assessment === "SIMULATED"
        ? t.simulated
        : t.anonymous;

  return (
    <div className="grid gap-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Fact label={t.model} value={snapshot.model ?? "—"} />
        <Fact label={t.firmware} value={snapshot.firmware ?? "—"} />
        <Fact label={t.origin} value={snapshot.origin} mono />
        <Fact label={t.identity} value={identityLabel} />
      </div>
      <div className="rounded-[var(--radius-lg)] bg-surface border border-border p-5">
        <p className="text-sm text-muted mb-3">{t.apis}</p>
        <div className="flex flex-wrap gap-2">
          <Pill ok={api.hiUtils} label="HiUtils" />
          <Pill ok={api.installApp} label="installApp" />
          <Pill ok={api.installAppV2} label="installApp_V2" />
          <Pill ok={api.omi} label="omi_platform" />
          <Pill ok={api.fileRead} label="fileRead" />
          <Pill ok={api.fileWrite} label="fileWrite" />
          <Pill ok={api.getInstalledApps} label="getInstalledApps" />
        </div>
      </div>
      <div className="rounded-[var(--radius-lg)] bg-surface border border-border p-5">
        <p className="text-sm text-muted mb-3">
          {t.apps} · {snapshot.installed.length}
        </p>
        <ul className="grid gap-2">
          {snapshot.installed.map((app) => (
            <li
              key={app.Id}
              className="flex flex-wrap items-baseline justify-between gap-2 border-b border-border/70 py-2 last:border-0"
            >
              <span className="font-medium">{app.AppName}</span>
              <span className="text-xs text-muted font-mono">
                {app.Id} · {app.StoreType}
              </span>
            </li>
          ))}
        </ul>
        {snapshot.appInfoError ? (
          <p className="mt-3 text-sm text-danger">{snapshot.appInfoError}</p>
        ) : null}
      </div>
      <div className="flex flex-wrap gap-3">
        <Button variant="primary" onClick={() => setView("install")}>
          <Tv className="size-5" />
          {t.install}
        </Button>
        <Button variant="secondary" onClick={() => setSnapshot(takeSnapshot())}>
          <Radar className="size-5" />
          {t.scan}
        </Button>
      </div>
    </div>
  );
}

function Fact({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="rounded-[var(--radius-lg)] bg-surface border border-border p-4">
      <p className="text-xs uppercase tracking-[0.14em] text-muted">{label}</p>
      <p className={cn("mt-2 text-lg leading-snug break-all", mono && "font-mono text-base")}>
        {value}
      </p>
    </div>
  );
}
