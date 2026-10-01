/* Adapted from Kimi's v2 report/UI transport. No TV filesystem or native calls. */
(function () {
  "use strict";
  var names = ["fetch", "Promise", "URL", "AbortController", "TextEncoder", "localStorage",
    "serviceWorker", "Hisense_GetModelName", "Hisense_GetFirmWareVersion", "Hisense_GetOSVersion"];
  var observations = ["launcher", "remote", "persisted", "pcOff", "playback"];

  function descriptorType(root, name) {
    try {
      for (var depth = 0; root && depth < 8; depth++, root = Object.getPrototypeOf(root)) {
        var descriptor = Object.getOwnPropertyDescriptor(root, name);
        if (!descriptor) continue;
        if (descriptor.get || descriptor.set) return "accessor";
        var type = typeof descriptor.value;
        return type === "function" || type === "object" ? type : "other";
      }
      return "absent";
    } catch (_) { return "unknown"; }
  }

  function makeReport(root, phase, provenance, values, reboot) {
    var report = { kind: "vidaa-readiness-v2", readOnly: true, phase: phase,
      timestamp: new Date().toISOString(), collectionId: provenance.collectionId,
      clientBuildId: provenance.buildId,
      accessContext: { origin: root.location.origin, secureContext: !!root.isSecureContext } };
    if (phase === "probe") {
      report.capabilities = {};
      names.forEach(function (name) {
        report.capabilities[name] = descriptorType(name === "serviceWorker" ? root.navigator : root, name);
      });
    } else {
      report.observations = {};
      observations.forEach(function (name) { report.observations[name] = values[name]; });
      report.rebootConfirmed = reboot === true;
    }
    return report;
  }

  function navigate(event, doc) {
    var code = event.keyCode || event.which;
    var key = event.key || ({37:"ArrowLeft",38:"ArrowUp",39:"ArrowRight",40:"ArrowDown",13:"Enter",461:"Escape"})[code];
    var controls = Array.prototype.slice.call(doc.querySelectorAll("button,select,input,summary"))
      .filter(function (element) { return !element.disabled && !element.hidden && element.getClientRects().length; });
    var active = doc.activeElement, index = controls.indexOf(active);
    if (active && active.tagName === "SELECT" && (key === "ArrowLeft" || key === "ArrowRight")) {
      event.preventDefault();
      active.selectedIndex = Math.max(0, Math.min(active.options.length - 1,
        active.selectedIndex + (key === "ArrowRight" ? 1 : -1)));
      return;
    }
    if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].indexOf(key) >= 0 && controls.length) {
      event.preventDefault();
      var backwards = key === "ArrowUp" || key === "ArrowLeft";
      controls[index < 0 ? 0 : (index + (backwards ? -1 : 1) + controls.length) % controls.length].focus();
    } else if (key === "Enter" && active && active.tagName !== "SELECT") {
      event.preventDefault(); active.click();
    } else if ((key === "Escape" || key === "Backspace") && controls.length) {
      event.preventDefault(); controls[0].focus();
    }
  }

  if (typeof window === "undefined" && typeof module !== "undefined" && module.exports) {
    module.exports = { descriptorType: descriptorType, makeReport: makeReport, navigate: navigate }; return;
  }
  var doc = document, status = doc.getElementById("status"), retry = doc.getElementById("retry");
  var script = doc.currentScript || doc.getElementById("readiness-v2-script");
  var executedBuild = script ? new URL(script.src, location.href).searchParams.get("v") : null;
  var busy = false, pending = null;
  doc.getElementById("origin").textContent = location.origin;

  async function request(path, options) {
    var controller = new AbortController();
    var timer = setTimeout(function () { controller.abort(); }, 5000);
    try {
      var response = await fetch(path, Object.assign({cache:"no-store",redirect:"error",credentials:"omit",signal:controller.signal}, options));
      if (!response.ok) throw new Error("Ricevitore HTTP " + response.status);
      return await response.json();
    } finally { clearTimeout(timer); }
  }
  function setBusy(value) {
    busy = value;
    ["probe", "observe", "verify", "retry"].forEach(function (id) { doc.getElementById(id).disabled = value; });
  }
  async function upload() {
    var receipt = await request("/snapshot", {method:"POST",headers:{"Content-Type":"application/json"},body:pending});
    status.textContent = "Report salvato sul PC. " +
      (receipt.outcome === "ACCEPTANCE_REPORTED" ? "Tutti i requisiti sono dichiarati soddisfatti dall'utente." :
        receipt.outcome === "OBSERVATIONS_INCOMPLETE" ? "Restano requisiti non verificati o non soddisfatti." : "Informazioni del browser registrate.") +
      " Nessuna installazione verificata automaticamente.";
    pending = null; retry.hidden = true;
  }
  function guard(phase) {
    return async function (event) {
      event.preventDefault(); if (busy) return;
      if (pending) { status.textContent = "Invia prima il report in attesa con Riprova."; return; }
      var reboot = doc.getElementById("reboot").checked;
      if (phase === "verify" && !reboot) { status.textContent = "Conferma il riavvio elettrico effettuato prima di questa verifica."; return; }
      setBusy(true); status.textContent = "Raccolta del report…";
      try {
        var provenance = await request("/manifest");
        if (provenance.buildId !== executedBuild || provenance.mode !== "isolated-vidaa-readiness-v2") throw new Error("Pagina non aggiornata: ricarica prima di raccogliere.");
        doc.getElementById("target").textContent = "Destinazione: " + provenance.target.appName + " · " + provenance.target.appId;
        var values = {}; observations.forEach(function (name) { values[name] = doc.getElementById(name).value; });
        var report = makeReport(window, phase, provenance, values, reboot);
        pending = JSON.stringify(report); doc.getElementById("details").textContent = JSON.stringify(report, null, 2);
        await upload();
      } catch (error) {
        status.textContent = "Raccolta o invio non riusciti: " + error.message;
        retry.hidden = !pending;
      } finally { setBusy(false); }
    };
  }
  ["probe", "observe", "verify"].forEach(function (id) { doc.getElementById(id).addEventListener("click", guard(id)); });
  retry.addEventListener("click", async function (event) {
    event.preventDefault(); if (busy || !pending) return;
    setBusy(true);
    try { await upload(); } catch (error) { status.textContent = "Invio non riuscito: " + error.message; }
    finally { setBusy(false); }
  });
  doc.addEventListener("keydown", function (event) { navigate(event, doc); });
  // Loading the page alone does not issue requests or acquire a report.
  doc.getElementById("target").textContent = "Destinazione Nuvio: verrà letta dal profilo Sidee al primo report.";
}());
