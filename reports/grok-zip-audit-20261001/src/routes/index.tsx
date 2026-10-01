import { createFileRoute } from "@tanstack/react-router";
import { GuideView } from "@/components/tv/guide-view";
import { HomeView } from "@/components/tv/home-view";
import { InstallView } from "@/components/tv/install-view";
import { ScanView } from "@/components/tv/scan-view";
import { Shell } from "@/components/tv/shell";
import { useTvKeys } from "@/components/tv/use-tv-keys";
import { copy } from "@/lib/vidaa/i18n";
import { useAppStore } from "@/lib/vidaa/store";

export const Route = createFileRoute("/")({ component: Home });

function Home() {
  const view = useAppStore((s) => s.view);
  const fhd = useAppStore((s) => s.fhd);
  const lang = useAppStore((s) => s.lang);
  const setFhd = useAppStore((s) => s.setFhd);
  const setView = useAppStore((s) => s.setView);
  const t = copy[lang];

  useTvKeys({
    onBlue: () => setFhd(!fhd),
    onBack: () => setView("home"),
  });

  return (
    <Shell subtitle={t.tagline}>
      {view === "home" ? <HomeView /> : null}
      {view === "scan" ? <ScanView /> : null}
      {view === "install" ? <InstallView /> : null}
      {view === "guide" ? <GuideView /> : null}
    </Shell>
  );
}
