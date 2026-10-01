import { makeAppEntry } from "./profile";
import {
  installAppLegacy,
  loadBackup,
  readAppInfo,
  rememberBackup,
  sendOmiUpdate,
  writeAppInfo,
} from "./bridge";
import type { InstallReport, InstallStep, StepStatus, TargetProfile } from "./types";

function step(id: string, label: string): InstallStep {
  return { id, label, status: "idle", detail: "" };
}

function set(steps: InstallStep[], id: string, status: StepStatus, detail: string) {
  const found = steps.find((s) => s.id === id);
  if (found) {
    found.status = status;
    found.detail = detail;
  }
}

function isAppConfigReject(msg: string, code?: number) {
  return code === 503 || /permission check|appconfig/i.test(msg);
}

export async function runFhdInstall(
  profile: TargetProfile,
  fhd: boolean,
  onChange?: (steps: InstallStep[]) => void,
): Promise<InstallReport> {
  const steps: InstallStep[] = [
    step("backup", "Backup Appinfo.json"),
    step("merge", "Inserimento tile Nuvio"),
    step("write", "fileWrite websdk/Appinfo.json"),
    step("omi", "OMI AllAppsUpdate"),
    step("legacy", "Hisense_installApp (extra)"),
    step("verify", "Verifica in Appinfo"),
  ];
  const ping = () => onChange?.(steps.map((s) => ({ ...s })));
  const startedAt = new Date().toISOString();
  const storeType = fhd ? "hisense" : "store";
  const target = { ...profile, storeType };
  const entry = makeAppEntry(target);
  let permissionMessage: string | null = null;

  set(steps, "backup", "running", "Lettura registro…");
  ping();
  const before = readAppInfo();
  if (!before.file || !before.raw) {
    set(steps, "backup", "fail", before.error || "Appinfo illeggibile");
    ping();
    return finish("UNKNOWN", false);
  }
  rememberBackup(before.raw);
  set(
    steps,
    "backup",
    "ok",
    `${before.file.AppInfo.length} app · backup sessione salvato`,
  );
  ping();

  set(steps, "merge", "running", `Id ${entry.Id} · StoreType ${storeType}`);
  ping();
  const next = structuredClone(before.file);
  const idx = next.AppInfo.findIndex((a) => a.Id === entry.Id || a.URL === entry.URL);
  if (idx >= 0) next.AppInfo[idx] = entry;
  else next.AppInfo.push(entry);
  set(
    steps,
    "merge",
    "ok",
    idx >= 0 ? "Entry esistente aggiornata" : "Nuova entry in coda al launcher",
  );
  ping();

  set(steps, "write", "running", fhd ? "FHD hisense" : "store");
  ping();
  const written = writeAppInfo(next);
  if (written.ret) {
    set(steps, "write", "ok", written.msg || "ret:true");
  } else {
    permissionMessage = written.msg;
    const rejected = isAppConfigReject(written.msg, written.code);
    set(
      steps,
      "write",
      rejected ? "fail" : "fail",
      `ret:false code:${written.code ?? "?"} · ${written.msg}`,
    );
  }
  ping();

  set(steps, "omi", "running", "sendPlatformMessage");
  ping();
  const omi = sendOmiUpdate(entry, storeType);
  set(steps, "omi", omi.ok ? "ok" : "warn", omi.detail);
  ping();

  set(steps, "legacy", "running", "callback 0 non è successo");
  ping();
  const legacy = await installAppLegacy(target);
  if (legacy.error) {
    set(steps, "legacy", "skip", legacy.error);
  } else if (legacy.callback === 0) {
    set(
      steps,
      "legacy",
      "warn",
      "callback 0 = richiesta accettata, non verifica. SIDEE non la conta come installata.",
    );
  } else {
    set(steps, "legacy", "warn", `callback ${String(legacy.callback)}`);
  }
  ping();

  set(steps, "verify", "running", "Rilettura Appinfo");
  ping();
  const after = readAppInfo();
  const found = after.file?.AppInfo.some(
    (a) => a.Id === entry.Id || a.URL === entry.URL || a.AppName === entry.AppName,
  );
  if (found && written.ret) {
    set(steps, "verify", "ok", "Nuvio presente in Appinfo dopo write");
  } else if (found && !written.ret) {
    set(steps, "verify", "warn", "Presente in lettura ma write aveva fallito — non affidabile");
  } else {
    set(steps, "verify", "fail", after.error || "Nuvio assente da Appinfo");
  }
  ping();

  const verified = Boolean(found && written.ret);
  const classification = verified
    ? "VERIFIED INSTALLED"
    : isAppConfigReject(written.msg, written.code)
      ? "REJECTED"
      : found
        ? "REQUESTED"
        : "NOT INSTALLED";
  return finish(classification, verified);

  function finish(
    classification: InstallReport["classification"],
    verified: boolean,
  ): InstallReport {
    return {
      startedAt,
      finishedAt: new Date().toISOString(),
      fhd,
      storeType,
      profile: target,
      steps: steps.map((s) => ({ ...s })),
      verified,
      classification,
      permissionMessage,
    };
  }
}

export function restoreBackup(): { ok: boolean; detail: string } {
  const raw = loadBackup();
  if (!raw) return { ok: false, detail: "Nessun backup di sessione" };
  try {
    const file = JSON.parse(raw);
    const result = writeAppInfo(file, "restore");
    return {
      ok: result.ret,
      detail: result.ret ? "Backup ripristinato" : result.msg,
    };
  } catch (err) {
    return { ok: false, detail: String(err) };
  }
}
