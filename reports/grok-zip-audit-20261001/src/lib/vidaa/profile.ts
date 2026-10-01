import type { TargetProfile } from "./types";

export const NUVIO_PRESETS: { id: string; label: string; profile: TargetProfile }[] = [
  {
    id: "hosted",
    label: "Nuvio TV hosted",
    profile: {
      appId: "nuviodebug",
      appName: "Nuvio TV",
      appUrl: "https://web.nuvioapp.space/?wrapper=vidaa",
      iconUrl: "",
      storeType: "hisense",
    },
  },
  {
    id: "web",
    label: "Nuvio web",
    profile: {
      appId: "nuviodebug",
      appName: "Nuvio TV",
      appUrl: "https://app.nuvio.tv/",
      iconUrl: "",
      storeType: "hisense",
    },
  },
  {
    id: "lan",
    label: "LAN Sidee (192.168.1.5)",
    profile: {
      appId: "nuviodebug",
      appName: "Nuvio TV",
      appUrl: "http://192.168.1.5:4173/?wrapper=vidaa",
      iconUrl: "http://192.168.1.5:4173/assets/images/icon.png",
      storeType: "hisense",
    },
  },
];

export const DEFAULT_PROFILE: TargetProfile = {
  ...NUVIO_PRESETS[0].profile,
};

export function withAbsoluteIcon(profile: TargetProfile, origin: string): TargetProfile {
  const iconUrl =
    profile.iconUrl && profile.iconUrl.length > 0
      ? profile.iconUrl
      : new URL("/nuvio-icon.png", origin).href;
  return { ...profile, iconUrl };
}

export function makeAppEntry(profile: TargetProfile): import("./types").AppEntry {
  const icon = profile.iconUrl;
  const today = new Date().toISOString().split("T")[0] ?? "";
  return {
    Id: profile.appId,
    AppName: profile.appName,
    Title: profile.appName,
    URL: profile.appUrl,
    StartCommand: profile.appUrl,
    IconURL: icon,
    Icon_96: icon,
    Image: icon,
    Thumb: icon,
    InstallTime: today,
    RunTimes: 0,
    StoreType: profile.storeType,
    PreInstall: false,
  };
}
