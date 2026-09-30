"""Summarize selected existing reports offline. No network or TV operations."""
import argparse
import hashlib
import json
from pathlib import Path

REPORTS = [
    "sidee-session-20260925-195421-ff60.json",
    "sidee-session-20260926-150815-b6a2.json",
    "sidee-session-20260926-153038-1083.json",
    "sidee-session-20260926-160944-2811.json",
    "sidee-session-20260926-161255-410f.json",
    "post-store-20260930-120901-112525.json",
]


def result_fields(value):
    return {k: value[k] for k in ("ret", "code") if k in value}


def summarize(path):
    data = path.read_bytes()
    report = json.loads(data.decode("utf-8-sig"))
    environment = report.get("environment") or {}
    device = environment.get("device") or {}
    context = report.get("accessContext") or {}
    origin = context.get("origin") or device.get("origin")
    row = {
        "file": path.name,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "updatedAt": report.get("updatedAt") or report.get("timestamp"),
        "receivedAt": report.get("receivedAt"),
        "origin": origin,
        "accessMode": report.get("accessMode"),
        "clientBuildId": report.get("clientBuildId"),
        "serverBuildId": report.get("serverBuildId"),
        "buildMatch": report.get("buildMatch"),
        "apiAvailability": environment.get("capabilities") or {},
        "permissionResults": [],
    }
    for attempt in (report.get("installDiagnostic") or {}).get("attempts", []):
        internal = attempt.get("internal") or {}
        backend = []
        for call in attempt.get("hiUtilsTrace") or []:
            result = call.get("result") or {}
            backend.append({
                "operation": call.get("type"),
                **result_fields(result),
                "sdkVersion": result.get("sdkVersion"),
                "appConfigPermissionFailure": result.get("ret") is False
                    and "appconfig" in str(result.get("msg", "")).lower(),
            })
        row["permissionResults"].append({
            "operation": attempt.get("method"),
            "timestamp": attempt.get("timestamp"),
            "callbackCode": (attempt.get("callback") or {}).get("code"),
            "returnValue": attempt.get("returnValue"),
            "classification": attempt.get("classification"),
            "ret": internal.get("internalRet"),
            "code": internal.get("errorCode"),
            "appConfigPermissionFailure": internal.get("appConfigPermissionFailure"),
            "backendOperations": backend,
        })
    globals_by_name = {entry.get("name"): entry for entry in environment.get("globals") or []}
    sources = {name: (globals_by_name.get(name) or {}).get("source") for name in
               ("Hisense_installApp", "Hisense_installApp_V2", "writeInstallAppObjToJson")}
    if all(isinstance(source, str) for source in sources.values()):
        row["installWrapperEvidence"] = {
            "sourceSha256": {name: hashlib.sha256(source.encode("utf-8")).hexdigest()
                             for name, source in sources.items()},
            "bothCallSameWriteHelper": all("writeInstallAppObjToJson" in sources[name]
                                           for name in ("Hisense_installApp", "Hisense_installApp_V2")),
            "helperUsesInstallApplication": "installApplication" in sources["writeInstallAppObjToJson"],
            "v2HasObjectTypeGuardAndMinusOneCallback": all(marker in sources["Hisense_installApp_V2"]
                for marker in ("typeof (appinfo) != 'object'", "callback(-1)")),
        }
    lab = report.get("directAppInfoWriteLab") or {}
    if lab:
        result = (lab.get("response") or {}).get("result") or {}
        row["permissionResults"].append({
            "operation": "historical-noop-write",
            "timestamp": lab.get("timestamp"),
            "classification": lab.get("writeCapability"),
            **result_fields(result),
            "readbackIdentical": lab.get("identicalBeforeAfter"),
        })
    gate = report.get("identityWriteGateLab") or {}
    if gate.get("baselineWrite"):
        baseline = gate["baselineWrite"]
        row["permissionResults"].append({
            "operation": "historical-baseline-noop-write",
            "timestamp": gate.get("timestamp"),
            **result_fields(baseline.get("result") or {}),
            "readbackIdentical": (baseline.get("readback") or {}).get("identical"),
        })
    fingerprint = report.get("contextIdentityFingerprint") or {}
    if fingerprint:
        row["apiAvailability"] = fingerprint.get("capabilities") or {}
        identity = fingerprint.get("identity") or {}
        row["nativeIdentityPresent"] = bool((identity.get("appId") or {}).get("value"))
        row["supportAppConfig"] = (identity.get("supportAppConfig") or {}).get("value")
    native_lab = report.get("appContextNoopWriteLab") or {}
    if native_lab:
        row["permissionResults"].append({
            "operation": "historical-native-noop-write",
            "timestamp": native_lab.get("timestamp"),
            "classification": native_lab.get("writeCapability"),
            **result_fields(native_lab.get("writeResponse") or {}),
            "readbackIdentical": (native_lab.get("readback") or {}).get("identicalToBackup"),
        })
    if "apps" in report:
        row["appInventoryStatus"] = report["apps"].get("status")
        row["packageInventoryStatus"] = report["packages"].get("status")
        row["packageCount"] = report["packages"].get("count")
    records = ((report.get("installedAppMetadata") or {}).get("appInfoDeepDump") or {}).get("records") or []
    for record in records:
        if str(record.get("Id")) == "1876":
            appinfo = record.get("appInfo") or {}
            row["historicalDuplecast"] = {
                "packaged": appinfo.get("packaged"),
                "appBundleEmpty": appinfo.get("appBundle") == "",
                "remoteStartCommand": str(record.get("StartCommand", "")).startswith("http"),
            }
    return row


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports", type=Path, default=Path(__file__).resolve().parents[1] / "reports")
    args = parser.parse_args()
    rows = []
    for name in REPORTS:
        path = args.reports / name
        rows.append(summarize(path) if path.is_file() else {"file": name, "missing": True})
    print(json.dumps({
        "kind": "saved-context-comparison-v1",
        "offline": True,
        "limits": [
            "Missing fields mean unrecorded, not unavailable or unauthorized.",
            "Build equality does not establish identical native context or an origin-only A/B.",
            "No credentials, native identifiers, raw registry or resource bytes exported.",
            "No historical firmware update A/B or new TV acceptance test.",
            "Wrapper evidence records source markers and hashes, not execution of captured functions.",
            "Permission denial does not establish that all later payload validation would pass.",
        ],
        "observations": rows,
    }, ensure_ascii=False, indent=2))
