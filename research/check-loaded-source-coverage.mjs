// Coverage only: no captured function execution, TV, network or credentials.
import { readdirSync, readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import path from "node:path";

const root = path.resolve(process.argv[2] || "reports");
const targets = ["window.HiUtils_createRequest", "window.writeInstallAppObjToJson",
  "window.Hisense_installApp", "window.Hisense_installApp_V2", "window.mapAppInfoFields",
  "window.vowOS.store.installApp", "window.vowOS.store.sendPkgmgrRequest",
  "window.vowOS.service.syncExecute", "window.vowOS.service.executeHttpRequest",
  "window.vowOS.service.execute"];
const bodies = new Map(targets.map(name => [name, new Map()]));
const scriptObservations = [], reports = [];
let timingRecorded = false;
const sha = value => createHash("sha256").update(value).digest("hex");
function visit(value, file, location) {
  if (/timingStatus|resourceTiming|performanceResources/.test(location)) timingRecorded = true;
  if (!value || typeof value !== "object") return;
  if (bodies.has(value.path) && typeof value.source === "string") {
    const source = value.source;
    bodies.get(value.path).set(sha(source), { file, chars: source.length, sha256: sha(source),
      clippingMarker: /\[truncated|…$/.test(source), representation: "Function.toString text; historical length often unrecorded" });
  }
  if (/loadedScripts$/.test(location) && Array.isArray(value.entries)) {
    scriptObservations.push({file, statuses: value.entries.map(item => item.status),
      nonSideeScriptCount: value.entries.filter(item => item.status !== "SIDEE_SELF_SKIPPED").length});
  }
  if (/legacyHspdkContext\.scripts$/.test(location) && Array.isArray(value)) {
    scriptObservations.push({file, surface: "legacyHspdkContext.scripts",
      scriptCount: value.length, explicitlySideeOwned: value.filter(item => item.sideeOwned === true).length});
  }
  for (const [key, child] of Object.entries(value)) visit(child, file, location + "." + key);
}
for (const file of readdirSync(root).filter(name => /^sidee-session-.*\.json$/.test(name)).sort()) {
  const raw = readFileSync(path.join(root, file));
  const report = JSON.parse(raw.toString("utf8").replace(/^\uFEFF/, ""));
  reports.push({file, sha256: sha(raw), bytes: raw.length});
  visit(report, file, "$" );
}
process.stdout.write(JSON.stringify({kind: "loaded-script-coverage-v1", offline: true,
  reportFilesRead: reports.length, reports, resourceTimingRecorded: timingRecorded,
  targets: Object.fromEntries([...bodies].map(([key, value]) => [key, [...value.values()]])),
  scriptObservations,
  gap: "Past document.scripts inspection does not cover scripts visible only through resource timing; no such timing was recorded.",
  limits: ["Copies are not independent TV sessions. No source bodies or client identifiers exported.",
    "Missing source means unrecorded, not absent. The map helper gap does not explain the observed permission denial.",
    "No native authorization implementation can be recovered by executing these JavaScript transport wrappers."]}, null, 2) + "\n");
