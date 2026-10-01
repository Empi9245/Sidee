(function () {
  "use strict";
  const MAX_SOURCE = 1024 * 1024, MAX_TOTAL = 4 * MAX_SOURCE, MAX_SCRIPTS = 12;
  const SELF = /\/(?:app|hspdk-context|post-store-check|nuvio-tv-check|bridge-source-check)\.js$/;
  // Omit entire source bodies containing credential literals; never redact a body
  // and then describe it as complete. Bare SDK property names are not secrets.
  const PRIVATE_LITERAL = /(?:token|secret|password|cookie|authorization|signature|credential|api[_-]?key)["']?\s*[:=]\s*["'`][^"'`\r\n]+["'`]|Bearer\s+[A-Za-z0-9._~+\/-]{8,}/i;
  function publicUrl(value, base) {
    try {
      const url = new URL(value, base);
      if (!/^https?:$/.test(url.protocol)) return { url: null, safe: false, protocol: url.protocol,
        origin: null, host: null, path: "" };
      const safe = !url.username && !url.password && !url.search && !url.hash;
      url.username = ""; url.password = ""; url.search = ""; url.hash = "";
      return { url: url.href, safe, protocol: url.protocol, origin: url.origin, host: url.hostname, path: url.pathname };
    } catch (_) { return null; }
  }
  function discover(root) {
    const entries = [], seen = new Set();
    let timingStatus = "UNAVAILABLE", timingCount = null, eligibleCount = 0;
    function add(value, via, inline) {
      const ref = inline ? null : publicUrl(value, root.location.href);
      const key = inline ? "inline:" + entries.length : ref && (ref.url || "scheme:" + ref.protocol);
      if (!inline && (!ref || seen.has(key))) return;
      seen.add(key);
      const owned = ref && ref.origin === root.location.origin && SELF.test(ref.path);
      const allowed = ref && /^https?:$/.test(ref.protocol) &&
        (ref.origin === root.location.origin || ref.host === "tvmodules-vidaa.vidaahub.com");
      if (!owned) eligibleCount++;
      if (entries.length >= 64) return;
      entries.push({ url: ref && ref.url, scheme: ref && ref.protocol, observedVia: via, inline: !!inline,
        status: owned ? "SIDEE_OWNED_SKIPPED" : inline ? "PENDING" :
          !/^https?:$/.test(ref.protocol) ? "OUT_OF_SCOPE" : !ref.safe ? "PRIVATE_URL_SKIPPED" : !allowed ? "OUT_OF_SCOPE" : "PENDING",
        observedQueryOmitted: ref ? !ref.safe : false, inlineText: inline || null });
    }
    for (const script of Array.from(root.document.scripts || []).slice(0, 64)) {
      if (script.src) add(script.src, "document.scripts", null);
      else if (script.textContent) add(null, "document.scripts", script.textContent);
    }
    try {
      const timings = root.performance.getEntriesByType("resource");
      timingStatus = "OBSERVED";
      const scripts = timings.filter(item => item.initiatorType === "script");
      timingCount = scripts.length;
      for (const item of scripts) add(item.name, "performance.resource", null);
    } catch (_) { /* Absence is recorded separately from an empty timeline. */ }
    return { entries, timingStatus, timingCount, eligibleCount,
      enumerationTruncated: entries.length >= 64 || (root.document.scripts || []).length > 64 };
  }
  async function readSource(url, fetcher, limit) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 5000);
    try {
      const response = await fetcher(url, { credentials: "omit", mode: "cors", redirect: "error",
        cache: "no-store", signal: controller.signal });
      if (response.status === 401 || response.status === 403) return { status: "DENIED", httpStatus: response.status };
      if (!response.ok) return { status: "UNAVAILABLE", httpStatus: response.status };
      if (!response.body || typeof response.body.getReader !== "function") return { status: "UNAVAILABLE", reason: "BOUNDED_STREAM_UNAVAILABLE" };
      const reader = response.body.getReader(), chunks = [];
      let size = 0, truncated = false;
      try {
        while (true) {
          const part = await reader.read();
          if (part.done) break;
          const remaining = limit - size;
          if (part.value.length > remaining) {
            chunks.push(part.value.slice(0, Math.max(0, remaining))); size += Math.max(0, remaining);
            truncated = true; await reader.cancel(); break;
          }
          chunks.push(part.value); size += part.value.length;
        }
      } finally { reader.releaseLock(); }
      const bytes = new Uint8Array(size); let offset = 0;
      for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
      let source;
      try { source = new TextDecoder("utf-8", { fatal: true }).decode(bytes); }
      catch (_) { return { status: truncated ? "TRUNCATED" : "UNAVAILABLE", receivedBytes: size, reason: "INVALID_OR_SPLIT_UTF8" }; }
      if (PRIVATE_LITERAL.test(source)) return { status: "SENSITIVE_SOURCE_OMITTED", receivedBytes: size };
      return { status: truncated ? "TRUNCATED" : size ? "COMPLETE" : "EMPTY",
        receivedBytes: size, source, complete: !truncated, httpStatus: response.status };
    } catch (_) {
      // A CORS/network/TLS rejection gives no readable HTTP status. Do not call it 403.
      return { status: "UNAVAILABLE", reason: controller.signal.aborted ? "TIMEOUT" : "NETWORK_CORS_OR_TLS" };
    } finally { clearTimeout(timer); }
  }
  async function collect(root, fetcher, provenance) {
    const discovery = discover(root), results = [];
    let total = 0, attempted = 0;
    for (const entry of discovery.entries) {
      const { inlineText, ...record } = entry;
      if (record.status === "PENDING") {
        if (attempted >= MAX_SCRIPTS || total >= MAX_TOTAL) record.status = "NOT_COLLECTED_LIMIT";
        else {
          attempted++;
          if (inlineText !== null) {
            const size = new TextEncoder().encode(inlineText).length;
            Object.assign(record, PRIVATE_LITERAL.test(inlineText) ? { status: "SENSITIVE_SOURCE_OMITTED" } :
              size > Math.min(MAX_SOURCE, MAX_TOTAL - total) ? { status: "TRUNCATED", reason: "INLINE_TOO_LARGE" } :
                { status: "COMPLETE", complete: true, source: inlineText, receivedBytes: size });
          } else Object.assign(record, await readSource(record.url, fetcher, Math.min(MAX_SOURCE, MAX_TOTAL - total)));
          total += record.receivedBytes || 0;
        }
      }
      results.push(record);
    }
    const nonOwned = results.filter(item => item.status !== "SIDEE_OWNED_SKIPPED");
    return { kind: "loaded-bridge-source-v1", readOnly: true, timestamp: new Date().toISOString(),
      collectionId: provenance.collectionId, clientBuildId: provenance.buildId,
      accessContext: { origin: root.location.origin, hostname: root.location.hostname,
        protocol: root.location.protocol, secureContext: !!root.isSecureContext },
      userAgent: String(root.navigator.userAgent || "").slice(0, 500),
      preferredContextObserved: root.location.hostname === "vidaahub.com",
      discovery: { timingStatus: discovery.timingStatus, timingCount: discovery.timingCount,
        eligibleCount: discovery.eligibleCount, enumerationTruncated: discovery.enumerationTruncated },
      sources: results, collectedBytes: total,
      outcome: nonOwned.length ? "OBSERVED_SOURCES" : "NO_NON_SIDEE_SCRIPT_OBSERVED",
      limits: ["Current page only; cannot inspect Store/system process or native injected code.",
        "Resource timing may omit scripts, earlier navigation or cleared/overflowed entries.",
        "GET only for observed script URLs, same origin or the known VIDAA device-script host; ordinary CORS applies.",
        "No SDK execution, native API call, identity, cookie, signing material, TV filesystem or installation.",
        "Source completeness is distinct from complete firmware coverage and authorization."] };
  }
  if (typeof window === "undefined" && typeof module !== "undefined" && module.exports) {
    module.exports = { collect, discover, readSource, PRIVATE_LITERAL }; return;
  }
  const button = document.getElementById("collect"), status = document.getElementById("status");
  const executedScript = document.currentScript || document.getElementById("bridge-source-script");
  const executedBuild = executedScript ? new URL(executedScript.src, location.href).searchParams.get("v") : null;
  let started = false, report = null;
  document.getElementById("origin").textContent = location.origin +
    (location.hostname === "vidaahub.com" ? " — contesto vidaahub" : " — contesto diverso da vidaahub; risultato separato");
  button.addEventListener("click", async function (event) {
    event.preventDefault();
    if (started) return;
    started = true; button.disabled = true;
    status.textContent = "Raccolta singola in corso…";
    try {
      const manifestResponse = await fetch("/manifest", { cache: "no-store", redirect: "error", credentials: "omit" });
      if (!manifestResponse.ok) throw new Error("Manifest indisponibile");
      const manifest = await manifestResponse.json();
      if (executedBuild !== manifest.buildId) throw new Error("Versione della pagina non aggiornata; ricarica prima di raccogliere");
      report = await collect(window, window.fetch.bind(window), manifest);
      const response = await fetch("/snapshot", { method: "POST", redirect: "error", credentials: "omit",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify(report) });
      if (!response.ok) throw new Error("Ricevitore HTTP " + response.status);
      const receipt = await response.json();
      status.textContent = "Raccolta salvata sul PC. Esito: " + report.outcome + ". Ricevuta: " + receipt.sha256;
    } catch (error) {
      status.textContent = "Raccolta o invio non riusciti: " + error.message;
      // Retain a collected result for explicit upload retry without another acquisition.
      if (report) document.getElementById("retry").hidden = false;
    }
  });
  document.getElementById("retry").addEventListener("click", async function (event) {
    event.preventDefault();
    if (!report) return;
    try {
      const response = await fetch("/snapshot", { method: "POST", redirect: "error", credentials: "omit",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify(report) });
      if (!response.ok) throw new Error("HTTP " + response.status);
      status.textContent = "Invio completato. Ricevuta: " + (await response.json()).sha256;
      document.getElementById("retry").hidden = true;
    } catch (error) { status.textContent = "Invio non riuscito: " + error.message; }
  });
}());
