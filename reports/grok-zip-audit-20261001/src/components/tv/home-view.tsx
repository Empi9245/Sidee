import { Button } from "@/components/ui/button";
import { copy } from "@/lib/vidaa/i18n";
import { NUVIO_PRESETS } from "@/lib/vidaa/profile";
import { takeSnapshot } from "@/lib/vidaa/bridge";
import { useAppStore } from "@/lib/vidaa/store";
import { BookOpen, Play, Radar, Tv } from "lucide-react";

export function HomeView() {
  const lang = useAppStore((s) => s.lang);
  const fhd = useAppStore((s) => s.fhd);
  const profile = useAppStore((s) => s.profile);
  const setView = useAppStore((s) => s.setView);
  const setSnapshot = useAppStore((s) => s.setSnapshot);
  const setProfile = useAppStore((s) => s.setProfile);
  const setBusy = useAppStore((s) => s.setBusy);
  const t = copy[lang];

  const scan = () => {
    setBusy(true);
    setSnapshot(takeSnapshot());
    setBusy(false);
    setView("scan");
  };

  return (
    <div className="grid gap-8 lg:grid-cols-[1.2fr_0.8fr]">
      <section className="rounded-[var(--radius-xl)] bg-surface border border-border p-6 md:p-8">
        <p className="text-xs uppercase tracking-[0.18em] text-muted">{t.brand} · VIDAA 9</p>
        <h1 className="font-display mt-3 text-4xl md:text-5xl leading-[1.1] tracking-tight">
          {t.tagline}
        </h1>
        <p className="mt-4 max-w-xl text-muted leading-relaxed">
          {t.fhdHint} {t.simNote}
        </p>
        <div className="mt-8 flex flex-col sm:flex-row gap-3">
          <Button variant="primary" onClick={scan} autoFocus>
            <Radar className="size-5" />
            {t.scan}
          </Button>
          <Button
            variant="secondary"
            onClick={() => {
              setSnapshot(takeSnapshot());
              setView("install");
            }}
          >
            <Tv className="size-5" />
            {t.install}
          </Button>
          <Button variant="ghost" onClick={() => window.location.assign(profile.appUrl)}>
            <Play className="size-5" />
            {t.watch}
          </Button>
        </div>
        <p className="mt-6 text-sm text-muted">
          {fhd ? t.fhdOn : t.fhdOff}
          <span className="mx-2 text-border-strong">·</span>
          {t.blueKey}
        </p>
      </section>

      <aside className="flex flex-col gap-4">
        <div className="rounded-[var(--radius-lg)] bg-raised border border-border p-5">
          <p className="text-sm text-muted">{t.target}</p>
          <p className="mt-1 font-display text-2xl">{profile.appName}</p>
          <p className="mt-2 break-all text-sm text-muted">{profile.appUrl}</p>
          <div className="mt-4 flex flex-col gap-2">
            {NUVIO_PRESETS.map((preset) => (
              <Button
                key={preset.id}
                size="md"
                variant={profile.appUrl === preset.profile.appUrl ? "primary" : "secondary"}
                onClick={() =>
                  setProfile({
                    ...preset.profile,
                    iconUrl: preset.profile.iconUrl,
                    storeType: fhd ? "hisense" : preset.profile.storeType,
                  })
                }
              >
                {preset.label}
              </Button>
            ))}
          </div>
        </div>
        <Button variant="secondary" onClick={() => setView("guide")}>
          <BookOpen className="size-5" />
          {t.guide}
        </Button>
        <div className="rounded-[var(--radius-lg)] border border-border p-5">
          <p className="text-sm font-medium">{t.proven}</p>
          <p className="mt-2 text-sm text-muted leading-relaxed">{t.provenBody}</p>
        </div>
      </aside>
    </div>
  );
}
