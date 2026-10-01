import type { AppEntry, AppInfoFile, HiUtilsResult, StoreType, TvSnapshot } from "./types";

type Win = Window &
  typeof globalThis & {
    Hisense_installApp?: (
      appId: string,
      appName: string,
      thumbnail: string,
      iconSmall: string,
      iconBig: string,
      appUrl: string,
      storeType: string,
      callback: (res: number) => void,
    ) => void;
    Hisense_installApp_V2?: (...args: unknown[]) => unknown;
    Hisense_uninstallApp?: (appId: string, callback: (ok: boolean) => void) => void;
    Hisense_getInstalledApps?: (callback: (apps: unknown) => void) => void;
    Hisense_GetFirmWareVersion?: () => string;
    Hisense_GetModelName?: () => string;
    Hisense_GetOSVersion?: () => string;
    Hisense_GetDeviceID?: () => string;
    Hisense_SupportAppConfig?: () => unknown;
    HiUtils_createRequest?: (action: string, params: Record<string, unknown>) => HiUtilsResult;
    omi_platform?: { sendPlatformMessage?: (msg: string) => unknown };
    opera_omi?: { sendPlatformMessage?: (msg: string) => unknown };
    vowOS?: { service?: { getIdentifier?: () => unknown } };
  };

const SIM_MODEL = "50E70LEVS_0003";
const SIM_FW = "V0000.09.60A.Q0707";

function seedAppInfo(): AppInfoFile {
  return {
    AppInfo: [
      entry("1470", "Smartone IPTV", "http://vidaa.smartone-iptv.com/", "store"),
      entry("1876", "Duplecast", "http://vidaa.duplecast.com/", "store"),
      entry("netflix", "Netflix", "https://www.netflix.com", "store", true),
    ],
  };
}

function entry(
  Id: string,
  AppName: string,
  URL: string,
  StoreType: StoreType,
  PreInstall = false,
): AppEntry {
  return {
    Id,
    AppName,
    Title: AppName,
    URL,
    StartCommand: URL,
    IconURL: "",
    Icon_96: "",
    Image: "",
    Thumb: "",
    InstallTime: "2025-01-01",
    RunTimes: 0,
    StoreType,
    PreInstall,
  };
}

const sim = {
  appInfo: seedAppInfo(),
  backup: "" as string,
};

function w(): Win {
  return window as Win;
}

export function isRealTv(): boolean {
  const x = w();
  return (
    typeof x.Hisense_GetFirmWareVersion === "function" ||
    typeof x.HiUtils_createRequest === "function" ||
    typeof x.Hisense_installApp === "function" ||
    typeof x.Hisense_GetOSVersion === "function"
  );
}

export function parseOsMajor(os: string | null): number | null {
  if (!os) return null;
  const n = Number.parseInt(String(os).replace(/^U0*/i, ""), 10);
  return Number.isFinite(n) ? n : null;
}

function safeCall<T>(fn: (() => T) | undefined): T | null {
  if (typeof fn !== "function") return null;
  try {
    return fn();
  } catch {
    return null;
  }
}

function asString(v: unknown): string | null {
  if (v == null) return null;
  const s = String(v).trim();
  return s.length ? s : null;
}

export function readAppInfo(): { file: AppInfoFile | null; error: string | null; raw: string | null } {
  const x = w();
  if (isRealTv()) {
    if (typeof x.HiUtils_createRequest !== "function") {
      return { file: null, error: "HiUtils_createRequest assente", raw: null };
    }
    try {
      const current = x.HiUtils_createRequest("fileRead", {
        path: "websdk/Appinfo.json",
        mode: 6,
      });
      if (!current?.ret) {
        return { file: null, error: current?.msg || "fileRead ret:false", raw: null };
      }
      const parsed = JSON.parse(current.msg) as AppInfoFile;
      if (!parsed || !Array.isArray(parsed.AppInfo)) {
        return { file: null, error: "JSON Appinfo senza AppInfo[]", raw: current.msg };
      }
      return { file: parsed, error: null, raw: current.msg };
    } catch (err) {
      return { file: null, error: String(err), raw: null };
    }
  }
  const raw = JSON.stringify(sim.appInfo);
  return { file: structuredClone(sim.appInfo), error: null, raw };
}

export function writeAppInfo(file: AppInfoFile, mode: "install" | "restore" = "install"): HiUtilsResult {
  const raw = JSON.stringify(file);
  const x = w();
  if (isRealTv()) {
    if (typeof x.HiUtils_createRequest !== "function") {
      return { ret: false, msg: "HiUtils_createRequest assente", code: 0 };
    }
    try {
      const result = x.HiUtils_createRequest("fileWrite", {
        path: "websdk/Appinfo.json",
        mode: 6,
        writedata: raw,
      });
      return {
        ret: Boolean(result?.ret),
        msg: String(result?.msg ?? ""),
        code: typeof result?.code === "number" ? result.code : undefined,
      };
    } catch (err) {
      return { ret: false, msg: String(err), code: 0 };
    }
  }
  const usesHisense = file.AppInfo.some((app) => String(app.StoreType) === "hisense");
  if (mode === "restore" || usesHisense) {
    sim.appInfo = JSON.parse(raw) as AppInfoFile;
    return { ret: true, msg: mode === "restore" ? "SIM_RESTORE_OK" : "SIM_WRITE_ALLOWED_FHD" };
  }
  return {
    ret: false,
    msg: "client request permission check error, please check appconfig",
    code: 503,
  };
}

export function sendOmiUpdate(app: AppEntry, storeType: string): { ok: boolean; detail: string } {
  const payload = {
    type: "APPMessage",
    MsgType: "appControl",
    action: "updateAppState",
    source: "browser",
    startAppType: 2,
    param: {
      event: "AllAppsUpdate",
      SubModuleName: "AllApps",
      startFrom: "",
      appInfo: {
        action: "install",
        Id: String(app.Id),
        Title: String(app.AppName),
        URL: String(app.URL),
        Image: String(app.Image || app.IconURL),
        StoreType: storeType || "hisense",
        provider: "",
        configUrl: "",
        configUrlDownload: 0,
        mediaId: 0,
        subCategory: "",
        categoryName: "",
      },
    },
  };
  const msg = JSON.stringify(payload);
  const x = w();
  if (x.omi_platform && typeof x.omi_platform.sendPlatformMessage === "function") {
    try {
      x.omi_platform.sendPlatformMessage(msg);
      return { ok: true, detail: "omi_platform AllAppsUpdate" };
    } catch (err) {
      return { ok: false, detail: String(err) };
    }
  }
  if (x.opera_omi && typeof x.opera_omi.sendPlatformMessage === "function") {
    try {
      x.opera_omi.sendPlatformMessage(msg);
      return { ok: true, detail: "opera_omi AllAppsUpdate" };
    } catch (err) {
      return { ok: false, detail: String(err) };
    }
  }
  if (!isRealTv()) return { ok: true, detail: "SIM omi_platform AllAppsUpdate" };
  return { ok: false, detail: "omi_platform assente" };
}

export function installAppLegacy(
  profile: {
    appId: string;
    appName: string;
    appUrl: string;
    iconUrl: string;
    storeType: string;
  },
): Promise<{ callback: number | null; error: string | null }> {
  const x = w();
  return new Promise((resolve) => {
    if (typeof x.Hisense_installApp !== "function") {
      if (!isRealTv()) {
        resolve({ callback: 0, error: null });
        return;
      }
      resolve({ callback: null, error: "Hisense_installApp assente" });
      return;
    }
    try {
      x.Hisense_installApp(
        profile.appId,
        profile.appName,
        profile.iconUrl,
        profile.iconUrl,
        profile.iconUrl,
        profile.appUrl,
        profile.storeType,
        (res) => resolve({ callback: res, error: null }),
      );
    } catch (err) {
      resolve({ callback: null, error: String(err) });
    }
  });
}

export function takeSnapshot(): TvSnapshot {
  const x = w();
  const real = isRealTv();
  const firmware = real ? asString(safeCall(x.Hisense_GetFirmWareVersion)) : SIM_FW;
  const model = real ? asString(safeCall(x.Hisense_GetModelName)) : SIM_MODEL;
  const osVersion = real ? asString(safeCall(x.Hisense_GetOSVersion)) : "U09";
  const deviceId = real ? asString(safeCall(x.Hisense_GetDeviceID)) : "SIM-Q0707";
  const appIdentifier = asString((navigator as Navigator & { appIdentifier?: unknown }).appIdentifier);
  const serviceIdentifier = asString(safeCall(x.vowOS?.service?.getIdentifier));
  const { file, error } = readAppInfo();
  const identityValues = [appIdentifier, serviceIdentifier].filter(Boolean);
  const assessment = real
    ? identityValues.length
      ? "IDENTITY PRESENT"
      : "ANONYMOUS-LIKE"
    : "SIMULATED";

  return {
    accessMode: real ? "real-tv" : "preview-sim",
    href: window.location.href,
    origin: window.location.origin,
    userAgent: navigator.userAgent,
    model,
    firmware,
    osVersion,
    osMajor: parseOsMajor(osVersion) ?? (real ? null : 9),
    deviceId,
    apis: {
      installApp: typeof x.Hisense_installApp === "function" || !real,
      installAppV2: typeof x.Hisense_installApp_V2 === "function",
      uninstallApp: typeof x.Hisense_uninstallApp === "function",
      getInstalledApps: typeof x.Hisense_getInstalledApps === "function",
      hiUtils: typeof x.HiUtils_createRequest === "function" || !real,
      omi: Boolean(x.omi_platform?.sendPlatformMessage) || !real,
      operaOmi: Boolean(x.opera_omi?.sendPlatformMessage),
      fileRead: typeof x.HiUtils_createRequest === "function" || !real,
      fileWrite: typeof x.HiUtils_createRequest === "function" || !real,
      getFirmware: typeof x.Hisense_GetFirmWareVersion === "function" || !real,
      getModel: typeof x.Hisense_GetModelName === "function" || !real,
      getOsVersion: typeof x.Hisense_GetOSVersion === "function" || !real,
      supportAppConfig: typeof x.Hisense_SupportAppConfig === "function",
    },
    identity: {
      appIdentifier,
      serviceIdentifier,
      assessment,
    },
    installed: file?.AppInfo ?? [],
    appInfo: file,
    appInfoError: error,
  };
}

export function resetSimulator() {
  sim.appInfo = seedAppInfo();
}

export function rememberBackup(raw: string) {
  sim.backup = raw;
  try {
    sessionStorage.setItem("sidee-nuvio9-backup", raw);
  } catch {
    /* ignore */
  }
}

export function loadBackup(): string | null {
  if (sim.backup) return sim.backup;
  try {
    return sessionStorage.getItem("sidee-nuvio9-backup");
  } catch {
    return null;
  }
}
