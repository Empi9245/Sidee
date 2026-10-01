export type StoreType = "store" | "hisense" | "custom";

export type AccessMode = "real-tv" | "preview-sim";

export interface AppEntry {
  Id: string;
  AppName: string;
  Title: string;
  URL: string;
  StartCommand: string;
  IconURL: string;
  Icon_96: string;
  Image: string;
  Thumb: string;
  Type?: string;
  InstallTime: string;
  RunTimes: number;
  StoreType: StoreType | string;
  PreInstall: boolean;
}

export interface AppInfoFile {
  AppInfo: AppEntry[];
}

export interface TargetProfile {
  appId: string;
  appName: string;
  appUrl: string;
  iconUrl: string;
  storeType: StoreType;
}

export interface TvSnapshot {
  accessMode: AccessMode;
  href: string;
  origin: string;
  userAgent: string;
  model: string | null;
  firmware: string | null;
  osVersion: string | null;
  osMajor: number | null;
  deviceId: string | null;
  apis: {
    installApp: boolean;
    installAppV2: boolean;
    uninstallApp: boolean;
    getInstalledApps: boolean;
    hiUtils: boolean;
    omi: boolean;
    operaOmi: boolean;
    fileRead: boolean;
    fileWrite: boolean;
    getFirmware: boolean;
    getModel: boolean;
    getOsVersion: boolean;
    supportAppConfig: boolean;
  };
  identity: {
    appIdentifier: string | null;
    serviceIdentifier: string | null;
    assessment: "IDENTITY PRESENT" | "ANONYMOUS-LIKE" | "INCOMPLETE" | "SIMULATED";
  };
  installed: AppEntry[];
  appInfo: AppInfoFile | null;
  appInfoError: string | null;
}

export type StepStatus = "idle" | "running" | "ok" | "warn" | "fail" | "skip";

export interface InstallStep {
  id: string;
  label: string;
  status: StepStatus;
  detail: string;
}

export interface HiUtilsResult {
  ret: boolean;
  msg: string;
  code?: number;
}

export interface InstallReport {
  startedAt: string;
  finishedAt: string;
  fhd: boolean;
  storeType: StoreType;
  profile: TargetProfile;
  steps: InstallStep[];
  verified: boolean;
  classification:
    | "VERIFIED INSTALLED"
    | "REQUESTED"
    | "REJECTED"
    | "NOT INSTALLED"
    | "UNKNOWN";
  permissionMessage: string | null;
}
