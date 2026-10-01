import { create } from "zustand";
import { DEFAULT_PROFILE } from "./profile";
import type { Lang } from "./i18n";
import type { InstallReport, InstallStep, TargetProfile, TvSnapshot } from "./types";

export type View = "home" | "scan" | "install" | "guide";

interface AppState {
  lang: Lang;
  view: View;
  fhd: boolean;
  profile: TargetProfile;
  snapshot: TvSnapshot | null;
  steps: InstallStep[];
  report: InstallReport | null;
  busy: boolean;
  setLang: (lang: Lang) => void;
  setView: (view: View) => void;
  setFhd: (fhd: boolean) => void;
  setProfile: (profile: TargetProfile) => void;
  setSnapshot: (snapshot: TvSnapshot | null) => void;
  setSteps: (steps: InstallStep[]) => void;
  setReport: (report: InstallReport | null) => void;
  setBusy: (busy: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  lang: "it",
  view: "home",
  fhd: true,
  profile: DEFAULT_PROFILE,
  snapshot: null,
  steps: [],
  report: null,
  busy: false,
  setLang: (lang) => set({ lang }),
  setView: (view) => set({ view }),
  setFhd: (fhd) => set({ fhd }),
  setProfile: (profile) => set({ profile }),
  setSnapshot: (snapshot) => set({ snapshot }),
  setSteps: (steps) => set({ steps }),
  setReport: (report) => set({ report }),
  setBusy: (busy) => set({ busy }),
}));
