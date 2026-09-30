// Offline semantics check of two reviewed TV wrappers. No TV/network access.
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { Script, createContext } from "node:vm";

const reportPath = process.argv[2];
if (!reportPath) throw new Error("Pass the saved 25 September TV report path.");
const bytes = readFileSync(reportPath);
const sha256 = (value) => createHash("sha256").update(value).digest("hex");
const expectedReportHash = "ae3eb5fba6cafffe8a14bb3aae7493634b27612b61158bea16dc2ffb073e1fba";
if (sha256(bytes) !== expectedReportHash) throw new Error("Saved report hash mismatch; review required.");
const report = JSON.parse(bytes.toString("utf8").replace(/^\uFEFF/, ""));
const labels = ["window.vowOS.store.installApp", "window.vowOS.store.sendPkgmgrRequest"];
const found = new Map(labels.map((label) => [label, new Set()]));
function collect(node) {
  if (!node || typeof node !== "object") return;
  if (found.has(node.path) && typeof node.source === "string") found.get(node.path).add(node.source);
  for (const value of Object.values(node)) if (value && typeof value === "object") collect(value);
}
collect(report);
const sources = Object.fromEntries(labels.map((label) => {
  const values = [...found.get(label)];
  if (values.length !== 1) throw new Error(`Expected one reviewed source for ${label}.`);
  return [label, values[0]];
}));
// Whole-input hash pins the exact source bodies that were reviewed in this session.
const storeSource = sources[labels[0]];
const requestSource = sources[labels[1]];
const scenarios = [];

function runScenario(name, packageBranch, packageAccepted, launcherAccepted) {
  const callbacks = [];
  const pending = [];
  let launcherCalls = 0;
  let transportCalls = 0;
  // This transport records a pending event only. It has no browser/network implementation.
  class FixtureRequest {
    open() { transportCalls += 1; }
    send() { pending.push(this); }
  }
  const context = createContext({
    console: { log() {} },
    XMLHttpRequest: FixtureRequest,
    Hisense_installApp(...args) {
      launcherCalls += 1;
      args[7](0); // Observed legacy callback behavior, even when registration fails.
      return launcherAccepted;
    },
    reportCallback(value) {
      // Retain status types only, never request arguments, identifiers or paths.
      callbacks.push(typeof value === "number"
        ? { kind: "legacy-code", code: value }
        : { kind: "result", ret: value?.ret });
    },
  }, { codeGeneration: { strings: false, wasm: false } });
  new Script(`const store = {
    installApp: (${storeSource}),
    sendPkgmgrRequest: (${requestSource})
  };
  const input = { appId: 'offline-fixture', appName: 'Offline fixture' };
  ${packageBranch ? "input.packageName = 'offline.fixture';" : ""}
  const initialReturn = store.installApp(input, reportCallback);`).runInContext(context, { timeout: 1000 });
  const initialReturn = new Script("initialReturn").runInContext(context, { timeout: 1000 });
  const callbacksBeforeResponse = callbacks.length;
  for (const request of pending) {
    request.status = 200;
    request.responseText = JSON.stringify({ ret: packageAccepted, msg: "offline fixture" });
    request.onload();
  }
  if (packageBranch && (initialReturn !== true || callbacksBeforeResponse !== 0 || transportCalls !== 1)) {
    throw new Error("Unexpected asynchronous wrapper contract.");
  }
  if (launcherCalls !== (packageBranch ? Number(packageAccepted) : 1)) throw new Error("Unexpected launcher branch.");
  const lastResult = callbacks.filter((value) => value.kind === "result").at(-1);
  if (!lastResult || lastResult.ret !== (packageBranch ? packageAccepted : launcherAccepted)) {
    throw new Error("Unexpected callback contract.");
  }
  scenarios.push({
    name, packageBranch, simulatedPackageAccepted: packageBranch ? packageAccepted : null,
    simulatedLauncherAccepted: launcherCalls ? launcherAccepted : null,
    immediateReturn: initialReturn, callbacksBeforeResponse, callbacks, launcherCalls,
    callbackMasksLauncherFailure: packageBranch && packageAccepted && !launcherAccepted && lastResult.ret === true,
  });
}

runScenario("package-rejected", true, false, false);
runScenario("package-accepted-launcher-rejected", true, true, false);
runScenario("package-and-launcher-accepted", true, true, true);
runScenario("url-registration-rejected", false, false, false);
if (!scenarios[1].callbackMasksLauncherFailure) throw new Error("Expected masked registration failure.");

process.stdout.write(JSON.stringify({
  kind: "vidaa-install-wrapper-contract-v1", offline: true,
  sourceReportSha256: expectedReportHash,
  sourceSha256: Object.fromEntries(labels.map((label) => [label, sha256(sources[label])])),
  scenarios,
  limits: [
    "Only two reviewed JavaScript wrapper bodies execute in a fixture with no network or TV bridge.",
    "A package success response is synthetic; no package was staged, accepted, signed or installed.",
    "No firmware permission check implementation, app resource bytes or reboot behavior is tested.",
    "Neither true nor callback success alone proves launcher registration or resource persistence.",
  ],
}, null, 2) + "\n");
