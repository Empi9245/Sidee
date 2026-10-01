import { Button } from "@/components/ui/button";
import { copy } from "@/lib/vidaa/i18n";
import { takeSnapshot } from "@/lib/vidaa/bridge";
import { restoreBackup, runFhdInstall } from "@/lib/vidaa/install";
import { withAbsoluteIcon } from "@/lib/vidaa/profile";
import { useAppStore } from "@/lib/vidaa/store";
import { cn } from "@/lib/utils";
import { Check, RotateCcw, Tv, X } from "lucide-react";
import { useState } from "react";

export function InstallView() {
  const lang = useAppStore((s) => s.lang);
  const fhd = useAppStore((s) => s.fhd);
  const profile = useAppStore((s) => s.profile);
  const steps = useAppStore((s) => s.steps);
  const report = useAppStore((s) => s.report);
  const busy = useAppStore((s) => s.busy);
  const setBusy = useAppStore((s) => s.setBusy);
  const setSteps = useAppStore((s) => s.setSteps);
  const setReport = useAppStore((s) => s.setReport);
  const setSnapshot = useAppStore((s) => s.setSnapshot);
  const t = copy[lang];
  const [restoreMsg, setRestoreMsg] = useState<string | null>(null);

  const run = async () => {
    setBusy(true);
    setRestoreMsg(null);
    const target = withAbsoluteIcon(profile, window.location.origin);
    const result = await runFhdInstall(target, fhd, setSteps);
    setReport(result);
    setSnapshot(takeSnapshot());
    setBusy(false);
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_1fr]">
      <section className="rounded-[var(--radius-xl)] bg-surface border border-border p-6">
        <h2 className="font-display text-3xl tracking-tight">{t.install}</h2>
        <p className="mt-2 text-muted">{fhd ? t.fhdOn : t.fhdOff}</p>
        <p className="mt-3 break-all text-sm text-muted">{profile.appUrl}</p>
        <div className="mt-6 flex flex-col gap-3">
          <Button variant="primary" onClick={() => void run()} disabled={busy} autoFocus>
            <Tv className="size-5" />
            {busy ? t.running : t.runInstall}
          </Button>
          <Button
            variant="secondary"
            disabled={busy}
            onClick={() => {
              const r = restoreBackup();
              setRestoreMsg(r.detail);
              setSnapshot(takeSnapshot());
            }}
          >
            <RotateCcw className="size-5" />
            {t.restore}
          </Button>
        </div>
        {restoreMsg ? <p className="mt-3 text-sm text-muted">{restoreMsg}</p> : null}
        {report ? <ResultBanner report={report} verifiedLabel={t.verified} rejectedLabel={t.rejected} missingLabel={t.notInstalled} reboot={t.reboot} /> : null}
      </section>
      <section className="rounded-[var(--radius-xl)] bg-raised border border-border p-6">
        <h3 className="text-sm uppercase tracking-[0.16em] text-muted">{t.stepsTitle}</h3>
        <ol className="mt-4 grid gap-3">
          {steps.length === 0 ? (
            <li className="text-muted">{t.simNote}</li>
          ) : (
            steps.map((step) => (
              <li key={step.id} className="flex gap-3">
                <StatusDot status={step.status} />
                <div className="min-w-0">
                  <p className="font-medium">{step.label}</p>
                  {step.detail ? (
                    <p className="text-sm text-muted break-words">{step.detail}</p>
                  ) : null}
                </div>
              </li>
            ))
          )}
        </ol>
      </section>
    </div>
  );
}

function ResultBanner({
  report,
  verifiedLabel,
  rejectedLabel,
  missingLabel,
  reboot,
}: {
  report: import("@/lib/vidaa/types").InstallReport;
  verifiedLabel: string;
  rejectedLabel: string;
  missingLabel: string;
  reboot: string;
}) {
  const ok = report.classification === "VERIFIED INSTALLED";
  const rejected = report.classification === "REJECTED";
  return (
    <div
      className={cn(
        "mt-6 rounded-[var(--radius-md)] border p-4",
        ok && "border-ok/40 bg-ok/10",
        rejected && "border-danger/40 bg-danger/10",
        !ok && !rejected && "border-warn/40 bg-warn/10",
      )}
    >
      <p className="font-medium flex items-center gap-2">
        {ok ? <Check className="size-4" /> : <X className="size-4" />}
        {ok ? verifiedLabel : rejected ? rejectedLabel : missingLabel}
      </p>
      <p className="mt-1 text-sm text-muted">{report.classification}</p>
      {report.permissionMessage ? (
        <p className="mt-2 font-mono text-xs break-words">{report.permissionMessage}</p>
      ) : null}
      {ok ? <p className="mt-3 text-sm">{reboot}</p> : null}
    </div>
  );
}

function StatusDot({ status }: { status: string }) {
  const color =
    status === "ok"
      ? "bg-ok"
      : status === "fail"
        ? "bg-danger"
        : status === "warn"
          ? "bg-warn"
          : status === "running"
            ? "bg-accent animate-pulse"
            : "bg-border-strong";
  return <span className={cn("mt-1.5 size-2.5 shrink-0 rounded-full", color)} />;
}
