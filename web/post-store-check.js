(function () {
  "use strict";
  const appFields = ["Id", "AppId", "AppName", "Title", "Name", "URL", "StartCommand",
    "StoreType", "packaged", "packageName", "pkgName", "appBundle", "configUrlDownload"];
  const packageFields = ["name", "version", "type", "path"];
  function pick(record, fields) {
    const out = {};
    if (!record || typeof record !== "object") return out;
    for (const key of Object.keys(record)) {
      if (!fields.some(field => field.toLowerCase() === key.toLowerCase())) continue;
      const value = record[key];
      if (!["string", "number", "boolean"].includes(typeof value)) continue;
      if (typeof value === "string" && /^https?:\/\//i.test(value)) {
        try {
          const url = new URL(value);
          url.username = ""; url.password = ""; url.search = ""; url.hash = "";
          out[key] = url.toString().slice(0, 1000);
        } catch (_) { out[key] = "[invalid URL]"; }
      } else { out[key] = typeof value === "string" ? value.slice(0, 1000) : value; }
    }
    return out;
  }
  function readList(owner, name, fields) {
    if (!owner || typeof owner[name] !== "function") return {status: "UNAVAILABLE", items: []};
    try {
      let value = owner[name]();
      for (let depth = 0; depth < 5; depth++) {
        if (typeof value === "string") { value = JSON.parse(value); continue; }
        if (value && value.ret === false) return {status: "DENIED", code: value.code || null, items: []};
        if (Array.isArray(value)) return {status: "READ_OK", count: value.length, truncated: value.length > 1000,
          items: value.slice(0, 1000).map(record => pick(record, fields))};
        if (!value || typeof value !== "object") break;
        const key = ["msg", "AppInfo", "apps", "packages", "data"].find(key => value[key] !== undefined);
        if (!key) break;
        value = value[key];
      }
      return {status: "UNRECOGNIZED_RESPONSE", items: []};
    } catch (error) { return {status: "READ_ERROR", error: String(error.message || error).slice(0, 300), items: []}; }
  }
  function snapshot(root) {
    const apps = readList(root, "Hisense_getInstalledApps", appFields);
    const packages = readList(root.vowOS && root.vowOS.store, "getInstalledPkgs", packageFields);
    const targets = apps.items.filter(app => Object.values(app).some(value =>
      /^(1876|1470|2568|nuviodebug)$/.test(String(value)) || /duplecast|smartone|stremio|nuvio/i.test(String(value))));
    return {
      kind: "post-store-inventory-v1", timestamp: new Date().toISOString(), readOnly: true,
      apps: {status: apps.status, code: apps.code || null, count: apps.count ?? null,
        error: apps.error || null, targets},
      packages,
      limits: ["Only exposed inventory APIs; no TV files or resource bytes read.",
        "Package inventory alone does not establish app resource persistence or an authorized importer.",
        "No launcher, remote, reboot, server-off or Nuvio playback test performed."]
    };
  }
  // Export the parsing helpers for off-TV fixtures; the page opens no other API.
  if (typeof module !== "undefined" && module.exports) {
    module.exports = {snapshot}; return;
  }
  const report = snapshot(window);
  const status = document.getElementById("status");
  document.getElementById("result").textContent = JSON.stringify({apps: report.apps, packages: {
    status: report.packages.status, count: report.packages.count ?? null}}, null, 2);
  if (report.apps.status === "UNAVAILABLE" && report.packages.status === "UNAVAILABLE") {
    status.textContent = "Questo contesto non espone gli elenchi della TV. Nessun report TV salvato.";
    return;
  }
  fetch("/snapshot", {method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify(report)}).then(response => {
    if (!response.ok) throw new Error("HTTP " + response.status);
    status.textContent = "Elenchi salvati sul PC. Puoi chiudere questa pagina con Indietro.";
  }).catch(error => { status.textContent = "Salvataggio non riuscito: " + error.message; });
}());
