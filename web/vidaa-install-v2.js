/* Sidee — VIDAA install v2: metodo "New" migliorato per VIDAA U09.60 (Q0707).
 *
 * Differenza rispetto a vidaa-edge: il metodo New upstream chiama
 * HiUtils_createRequest('fileWrite'), che e' una RPC al servizio nativo
 * localhost:9009/service/hiutils e sui firmware 09.60 viene respinta con
 * AppConfig 503. Su VIDAA U09.01 (ztomer/hisense_vidaa, agosto 2026) la
 * scrittura riuscita usa invece il global DIRETTO Hisense_FileWrite, che non
 * passa dal servizio con controllo permessi. Su Q0707 la presenza dei global
 * diretti Hisense_FileRead/Hisense_FileWrite nel contesto vidaahub non e'
 * mai stata misurata: questa pagina la misura e, se presenti, li usa.
 *
 * Cascata scrittura: Hisense_FileWrite diretto -> File.write legacy ->
 * HiUtils fileWrite (noto 503, registrato come dato) -> canale pkgmgr ->
 * Hisense_installApp (solo registrazione URL; callback 0 NON e' successo:
 * verifica via readback).
 *
 * Canale pkgmgr (25 settembre, report ff60): vowOS.service.syncExecute e'
 * un POST sincrono a https://localhost:9888/service/<servizio> con header
 * "identifier" = vowOS.service.getIdentifier() (nel browser ritorna "":
 * la funzione nativa vowOSContext.getAppIdentifier resta opaca). I 503
 * AppConfig gia' osservati erano quindi con identifier vuoto. vowOS.store
 * espone comunque un canale DISTINTO da hiutils: getInstalledPkgs (lettura
 * pacchetti) e il ramo package di installApp (api 'install' con pkgName,
 * path file:///APPS/pkgs/<pkgName>/index.html). Su Q0707 questo canale non
 * e' mai stato misurato: i pacchetti di sistema (tv.vidaa.app.*, elenco del
 * 30 settembre) compaiono nel launcher da pkgmgr, non solo da Appinfo.json.
 * La prova di canale usa un nome pacchetto inesistente: atteso ret:false
 * senza effetti; poi un pacchetto reale gia' installato (nessun download).
 *
 * Laboratorio identifier: il canale raw riproduce la stessa richiesta POST
 * del wrapper con controllo esplicito dell'header identifier (proprietario
 * TV: esperimento autorizzato). Baseline "" (nota: 503 AppConfig), poi i
 * candidati osservati sulla TV: i pacchetti di sistema app/jsservice. Se un
 * candidato fa passare fileWrite, il registro scritto e' quello merge
 * protetto da backup+rilettura; se tutti falliscono si prova la stessa
 * griglia sull'API installApplication del wrapper legacy. Solo la rilettura
 * attesta il risultato, come per ogni altra primitiva.
 *
 * Merge lato TV: legge Appinfo.json, sostituisce la voce con lo stesso Id,
 * riscrive l'intero file, rilegge e verifica. Voci esistenti preservate.
 * MAI chiamare refreshAppsOnHisenseUI (remerge dai preset, rimuove la tile)
 * e MAI inviare dump grezzi ad AllAppsUpdate (incidente launcher ztomer).
 */
(function () {
  "use strict";

  // Il target arriva dal manifest generato da config.json sul PC.
  var target = null;

  var APPINFO_PATH = "websdk/Appinfo.json";
  var APPINFO_MODE = 6;
  var READ_MODES = [6, 1]; // 6 provato su U09.01; 1 era il modo dell'API File del 2020
  var RAW_PORT_OPTIONS = ["https://localhost:9888/service/", "http://localhost:9009/service/"];
  var FALLBACK_CANDIDATES = ["tv.vidaa.app.tvbrowser", "tv.vidaa.app.operationui",
    "tv.vidaa.app.phoenix", "tv.vidaa.jsservice.system"];
  var DETAIL_LIMIT = 600;
  var REGISTRY_LIMIT = 512 * 1024;

  var PRIVATE_LITERAL = /(?:token|secret|password|cookie|authorization|signature|credential|api[_-]?key)["']?\s*[:=]\s*["'`][^"'`\r\n]+["'`]|Bearer\s+[A-Za-z0-9._~+\/-]{8,}/i;

  var state = {
    probeReport: null,
    probeSaved: false,
    workingReader: null, // {name, read(path)->{ok,text,mode,denied,raw}}
    workingWriter: null, // {name, write(path,text)->{ok,denied,raw}}
    beforeText: null
  };

  function has(name) { return typeof window[name] === "function"; }
  function configureTarget(value) {
    if (!value || typeof value.appId !== "string" || typeof value.appName !== "string" ||
        typeof value.appUrl !== "string" || typeof value.iconUrl !== "string" ||
        typeof value.storeType !== "string") throw new Error("Target Nuvio non valido");
    target = value;
    return target;
  }
  function utf8Length(text) {
    if (typeof TextEncoder === "function") return new TextEncoder().encode(text).length;
    try { return unescape(encodeURIComponent(text)).length; } catch (_) { return text.length; }
  }
  function navigate(event, doc) {
    var code = event.keyCode || event.which;
    var key = event.key || ({37:"ArrowLeft",38:"ArrowUp",39:"ArrowRight",40:"ArrowDown",13:"Enter",461:"Escape"})[code];
    var controls = Array.prototype.slice.call(doc.querySelectorAll("button,input"))
      .filter(function (element) { return !element.disabled && !element.hidden && element.getClientRects().length; });
    var active = doc.activeElement, index = controls.indexOf(active);
    if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].indexOf(key) >= 0 && controls.length) {
      event.preventDefault();
      var backwards = key === "ArrowUp" || key === "ArrowLeft";
      controls[index < 0 ? 0 : (index + (backwards ? -1 : 1) + controls.length) % controls.length].focus();
    } else if (key === "Enter" && active) {
      event.preventDefault(); active.click();
    } else if ((key === "Escape" || key === "Backspace") && controls.length) {
      event.preventDefault(); controls[0].focus();
    }
  }
  function short(value, limit) {
    var s = typeof value === "string" ? value : String(value);
    return s.length > (limit || DETAIL_LIMIT) ? s.slice(0, limit || DETAIL_LIMIT) + "…[TRONCATO]" : s;
  }
  function summarize(obj) {
    try { return short(JSON.stringify(obj)); } catch (_) { return short(String(obj)); }
  }
  function sha256Text(text) {
    if (window.crypto && crypto.subtle && window.isSecureContext && typeof TextEncoder === "function") {
      return crypto.subtle.digest("SHA-256", new TextEncoder().encode(text)).then(function (buf) {
        return Array.from(new Uint8Array(buf)).map(function (b) { return ("0" + b.toString(16)).slice(-2); }).join("");
      });
    }
    return Promise.resolve(null); // contesto non sicuro: hash lasciato al ricevitore
  }

  // ---- Primitive disponibili ------------------------------------------------

  function detectCapabilities() {
    var caps = {
      XMLHttpRequest: typeof XMLHttpRequest === "function",
      Hisense_FileRead: has("Hisense_FileRead"),
      Hisense_FileWrite: has("Hisense_FileWrite"),
      File_object: typeof File !== "undefined" && !!File,
      File_read: typeof File !== "undefined" && !!File && typeof File.read === "function",
      File_write: typeof File !== "undefined" && !!File && typeof File.write === "function",
      HiUtils_createRequest: has("HiUtils_createRequest"),
      Hisense_installApp: has("Hisense_installApp"),
      Hisense_installApp_V2: has("Hisense_installApp_V2"),
      Hisense_getInstalledApps: has("Hisense_getInstalledApps"),
      getInstalledAppJsonObj: has("getInstalledAppJsonObj"),
      vowOS: typeof vowOS !== "undefined",
      vowOS_store: typeof vowOS !== "undefined" && !!(vowOS && vowOS.store),
      vowOS_store_getInstalledPkgs: typeof vowOS !== "undefined" && !!(vowOS && vowOS.store && typeof vowOS.store.getInstalledPkgs === "function"),
      vowOS_store_installApp: typeof vowOS !== "undefined" && !!(vowOS && vowOS.store && typeof vowOS.store.installApp === "function"),
      vowOS_store_sendPkgmgrRequest: typeof vowOS !== "undefined" && !!(vowOS && vowOS.store && typeof vowOS.store.sendPkgmgrRequest === "function")
    };
    return caps;
  }

  // Enumerazione bounded dei global pertinenti: e' il dato mai misurato su
  // Q0707 nel contesto vidaahub. Solo nomi di proprieta', nessuna esecuzione.
  function enumerateGlobals() {
    var names;
    try { names = Object.getOwnPropertyNames(window); } catch (_) { return { status: "UNAVAILABLE" }; }
    var matches = names.filter(function (n) {
      return /hisense|hiutils|vow|file|store|install|pkgmgr|odin|omi/i.test(n);
    }).sort();
    var truncated = matches.length > 200;
    return { status: "OK", totalWindowProps: names.length, matched: truncated ? matches.slice(0, 200) : matches, truncated: truncated };
  }

  function makeReaders() {
    var list = [];
    if (has("Hisense_FileRead")) {
      list.push({
        name: "Hisense_FileRead",
        read: function (path, mode) {
          var out = Hisense_FileRead(path, mode); // puo' lanciare o tornare non-stringa
          if (typeof out === "string" && out.length > 0) return { ok: true, text: out };
          return { ok: false, raw: "return:" + summarize(out) };
        }
      });
    }
    if (typeof File !== "undefined" && File && typeof File.read === "function") {
      list.push({
        name: "File.read",
        read: function (path, mode) {
          var out = File.read(path, mode);
          if (typeof out === "string" && out.length > 0) return { ok: true, text: out };
          return { ok: false, raw: "return:" + summarize(out) };
        }
      });
    }
    if (has("HiUtils_createRequest")) {
      list.push({
        name: "HiUtils fileRead",
        read: function (path, mode) {
          var r = HiUtils_createRequest("fileRead", { path: path, mode: mode });
          if (r && r.ret === true && typeof r.msg === "string") return { ok: true, text: r.msg, raw: summarize({ ret: r.ret, code: r.code, sdk: r.sdk }) };
          return { ok: false, denied: !!(r && r.ret === false), raw: summarize(r) };
        }
      });
    }
    return list;
  }

  function makeWriters() {
    var list = [];
    if (has("Hisense_FileWrite")) {
      list.push({
        name: "Hisense_FileWrite",
        write: function (path, text, mode) {
          var out = Hisense_FileWrite(path, text, mode);
          var ok = out === true || out === 1 || String(out) === "true";
          return { ok: ok, raw: "return:" + summarize(out) };
        }
      });
    }
    if (typeof File !== "undefined" && File && typeof File.write === "function") {
      list.push({
        name: "File.write",
        write: function (path, text, mode) {
          var out = File.write(path, text, mode);
          var ok = out === true || out === 1 || String(out) === "true";
          return { ok: ok, raw: "return:" + summarize(out) };
        }
      });
    }
    if (has("HiUtils_createRequest")) {
      list.push({
        name: "HiUtils fileWrite",
        write: function (path, text, mode) {
          var r = HiUtils_createRequest("fileWrite", { path: path, mode: mode, writedata: text });
          return { ok: !!(r && r.ret === true), denied: !!(r && r.ret === false), raw: summarize(r) };
        }
      });
    }
    return list;
  }

  // ---- Canale pkgmgr (servizio separato da hiutils) ------------------------

  function pkgmgrObservation() {
    // getInstalledPkgs e' la stessa chiamata che il report del 30 settembre
    // mostra usata dal contesto post-Store. Lettura, nessun parametro.
    if (typeof vowOS === "undefined" || !vowOS || !vowOS.store ||
        typeof vowOS.store.getInstalledPkgs !== "function") return { status: "UNAVAILABLE" };
    var result = { status: "CALLED", pkgCount: null, pkgNames: [], raw: null };
    try {
      var r = vowOS.store.getInstalledPkgs();
      result.raw = summarize(r);
      if (r && r.ret) {
        var list = r.msg && (r.msg.items || r.msg.pkgs || r.msg);
        if (Array.isArray(list)) {
          result.pkgCount = list.length;
          result.pkgNames = list.slice(0, 40).map(function (p) {
            return p && typeof p === "object" ? String(p.name || p.pkgName || p.Name || "?") : String(p);
          });
        }
      } else {
        result.status = "DENIED_OR_EMPTY";
      }
    } catch (error) {
      result.status = "EXCEPTION";
      result.raw = short(String(error));
    }
    return result;
  }

  function identifierProvenance() {
    // Come la pagina arriva all'identita' inviata nel canale HTTP: source JS
    // di getIdentifier + descriptor di navigator.appIdentifier. Nessun setter.
    var info = { getIdentifierSource: null, nativeContextResult: null, navigatorAppIdentifier: null };
    try {
      if (typeof vowOS !== "undefined" && vowOS && vowOS.service &&
          typeof vowOS.service.getIdentifier === "function") {
        info.getIdentifierSource = short(String(vowOS.service.getIdentifier));
      }
    } catch (_) { /* ispezione non disponibile */ }
    try {
      var descriptor = Object.getOwnPropertyDescriptor(Navigator.prototype, "appIdentifier") ||
        Object.getOwnPropertyDescriptor(navigator, "appIdentifier");
      if (descriptor) {
        info.navigatorAppIdentifier = {
          hasGetter: typeof descriptor.get === "function",
          hasSetter: typeof descriptor.set === "function"
        };
        if (descriptor.get) info.navigatorAppIdentifier.getterSource = short(String(descriptor.get));
        if (!descriptor.get && typeof descriptor.value !== "undefined") {
          info.navigatorAppIdentifier.value = short(String(descriptor.value));
        }
      }
    } catch (_) { /* ispezione non disponibile */ }
    try {
      if (typeof vowOSContext !== "undefined" && vowOSContext &&
          typeof vowOSContext.getAppIdentifier === "function") {
        // La stessa lettura che il bridge fa a ogni richiesta: sola identita'.
        info.nativeContextResult = short(JSON.stringify(vowOSContext.getAppIdentifier()));
      }
    } catch (error) {
      info.nativeContextResult = "exception:" + short(String(error));
    }
    return info;
  }

  function storeInstallPackage(pkgName, appId, attempts, label) {
    // Ramo package di vowOS.store.installApp: api 'install' verso pkgmgr,
    // DISTINTO da installApplication/hiutils dove il 503 e' noto. Il wrapper
    // chiama da solo Hisense_installApp solo dopo una risposta pkgmgr positiva.
    if (typeof vowOS === "undefined" || !vowOS || !vowOS.store ||
        typeof vowOS.store.installApp !== "function") {
      attempts.push({ primitive: "pkgmgr " + label, phase: "store-install", ok: false, detail: "vowOS.store.installApp assente" });
      return false;
    }
    return new Promise(function (resolve) {
      var payload = { appId: appId, appName: target.appName, appUrl: target.appUrl,
        iconSmall: target.iconUrl, iconBig: target.iconUrl, thumbnail: target.iconUrl,
        storetype: target.storeType, packageName: pkgName };
      var callbackResult = "NO_CALLBACK_ENTRO_TIMEOUT";
      var finished = false, finishTimer = null, earlyTimer = null;
      function finish() {
        if (finished) return;
        finished = true;
        if (finishTimer) clearTimeout(finishTimer);
        if (earlyTimer) clearTimeout(earlyTimer);
        var ok = !!(callbackResult && typeof callbackResult === "object" && callbackResult.ret === true);
        attempts.push({ primitive: "pkgmgr " + label, phase: "store-install", pkgName: pkgName,
          ok: ok,
          detail: summarize(callbackResult),
          note: "callback wrapper pkgmgr: {ret, msg:{appId, message}}. Vale solo il readback." });
        resolve(ok);
      }
      try {
        vowOS.store.installApp(payload, function (res) {
          callbackResult = res;
          // Il wrapper puo' chiamare il callback piu' volte (0 interno, poi
          // la risposta pkgmgr): l'ultimo valore entro la finestra vince.
          if (earlyTimer) clearTimeout(earlyTimer);
          earlyTimer = setTimeout(finish, 750);
        });
      } catch (error) {
        attempts.push({ primitive: "pkgmgr " + label, phase: "store-install", pkgName: pkgName,
          ok: false, detail: "exception:" + short(error && error.message ? error.message : String(error)) });
        return resolve(false);
      }
      finishTimer = setTimeout(finish, 4000);
    });
  }

  // ---- Canale raw del bus con identifier controllabile ----------------------

  var rawBus = {
    option: null,
    validated: false,
    request: function (service, api, args, identifier) {
      if (typeof XMLHttpRequest !== "function") {
        return { ok: false, unavailable: true, detail: "XMLHttpRequest assente" };
      }
      var body = JSON.stringify({ api: api, args: args });
      var options = this.validated ? [this.option] : RAW_PORT_OPTIONS;
      var last = null;
      for (var i = 0; i < options.length; i++) {
        var xhr = new XMLHttpRequest();
        try {
          // Sincrono come il wrapper originale: la risposta governa la fase.
          xhr.open("POST", options[i] + service, false);
          xhr.setRequestHeader("identifier", identifier);
          xhr.send(body);
          if (xhr.status === 200) {
            this.option = options[i];
            this.validated = true;
            var parsed = null;
            try { parsed = JSON.parse(xhr.responseText); } catch (_) { parsed = null; }
            return { ok: true, status: 200, body: parsed !== null ? parsed : short(String(xhr.responseText)) };
          }
          last = "status:" + xhr.status;
        } catch (error) {
          last = "exception:" + short(String(error && error.message ? error.message : String(error)));
        }
      }
      this.validated = true; // stesso comportamento del wrapper: non ritentare le porte
      return { ok: false, detail: last };
    }
  };

  function identifierCandidates() {
    // Candidati osservati sulla TV: pacchetti app/jsservice dall'osservazione
    // pkgmgr della fase Analizza; lista statica di riserva se la lettura
    // pkgmgr non e' disponibile. Nessun nome inventato.
    var pool = [], seen = {};
    function add(value) {
      value = String(value || "").trim();
      if (!value || seen[value]) return;
      seen[value] = true;
      pool.push(value);
    }
    var names = (state.probeReport && state.probeReport.pkgmgrObservation &&
      state.probeReport.pkgmgrObservation.pkgNames) || [];
    names.forEach(function (name) {
      if (/^tv\.vidaa\.(app|jsservice)\./.test(name)) add(name);
    });
    FALLBACK_CANDIDATES.forEach(add);
    return pool.slice(0, 6);
  }

  async function runIdentifierLab(path, mergedJson, attempts) {
    // Stessa richiesta del wrapper, header identifier selezionabile.
    // Primo tentativo con "" = baseline A/B sullo stesso canale (atteso il
    // 503 AppConfig noto), poi i candidati osservati. Se fileWrite non passa
    // con nessun candidato si applica la stessa griglia a installApplication,
    // l'API che il wrapper legacy usa per registrare il registro intero.
    var candidates = identifierCandidates();
    var result = { identifiersTried: [],
      writeSucceeded: false, registerSucceeded: false, baseline503: null };
    var grid = [""].concat(candidates);
    for (var i = 0; i < grid.length && !result.writeSucceeded; i++) {
      var value = grid[i];
      result.identifiersTried.push(value);
      var attempt = { primitive: "raw fileWrite identifier=" + (value || "<vuoto>"),
        phase: "write", path: path, mode: APPINFO_MODE };
      var response = rawBus.request("hiutils", "fileWrite",
        { path: path, mode: APPINFO_MODE, writedata: mergedJson }, value);
      attempt.ok = !!(response.ok && response.body && response.body.ret === true);
      attempt.detail = summarize(response);
      attempts.push(attempt);
      if (value === "" && response.ok && response.body && response.body.ret === false) {
        result.baseline503 = summarize(response.body.msg || response.body);
      }
      result.writeSucceeded = attempt.ok;
    }
    if (!result.writeSucceeded) {
      for (var j = 0; j < candidates.length && !result.registerSucceeded; j++) {
        var candidate = candidates[j];
        var registerAttempt = { primitive: "raw installApplication identifier=" + candidate,
          phase: "write", path: path, mode: APPINFO_MODE };
        var registerResponse = rawBus.request("hiutils", "installApplication", mergedJson, candidate);
        registerAttempt.ok = !!(registerResponse.ok && registerResponse.body && registerResponse.body.ret === true);
        registerAttempt.detail = summarize(registerResponse);
        attempts.push(registerAttempt);
        result.registerSucceeded = registerAttempt.ok;
      }
    }
    return result;
  }

  // ---- Merge lato TV (preserva le voci esistenti) ---------------------------

  function buildEntry() {
    if (!target) throw new Error("Target Nuvio non caricato");
    return {
      Id: target.appId,
      AppName: target.appName,
      Title: target.appName,
      URL: target.appUrl,
      StartCommand: target.appUrl,
      IconURL: target.iconUrl,
      Icon_96: target.iconUrl,
      Image: target.iconUrl,
      Thumb: target.iconUrl,
      Type: "Browser", // necessario: senza Type la tile non si apre (lezione ztomer)
      InstallTime: new Date().toISOString().split("T")[0],
      RunTimes: 0,
      StoreType: target.storeType,
      PreInstall: false
    };
  }

  function mergeRegistry(text) {
    if (!target) throw new Error("Target Nuvio non caricato");
    if (typeof text !== "string" || !text.trim()) throw new Error("Registro AppInfo vuoto");
    var registry = JSON.parse(text);
    if (!registry || typeof registry !== "object" || !Array.isArray(registry.AppInfo)) {
      throw new Error("Formato AppInfo non riconosciuto");
    }
    var apps = registry.AppInfo;
    var kept = apps.filter(function (a) {
      return !a || typeof a !== "object" ||
        (a.Id !== target.appId && a.appId !== target.appId && a.appid !== target.appId);
    });
    kept.push(buildEntry());
    registry.AppInfo = kept;
    return { json: JSON.stringify(registry), countBefore: apps.length, countAfter: kept.length };
  }

  function registrySummary(text) {
    var base = { bytes: 0, entryCount: null, ids: [], omitted: null, content: null };
    if (typeof text !== "string") return base;
    base.bytes = utf8Length(text);
    var valid = false;
    try {
      var registry = JSON.parse(text);
      if (!registry || typeof registry !== "object" || !Array.isArray(registry.AppInfo)) throw new Error("Invalid AppInfo");
      var apps = registry.AppInfo;
      base.entryCount = apps.length;
      base.ids = apps.map(function (a) { return { Id: a && a.Id, AppName: a && a.AppName, Type: a && a.Type }; }).slice(0, 100);
      valid = true;
    } catch (_) { base.omitted = "PARSE_ERROR"; }
    if (valid && base.bytes <= REGISTRY_LIMIT && !PRIVATE_LITERAL.test(text)) base.content = text;
    else if (valid) base.omitted = base.bytes > REGISTRY_LIMIT ? "TOO_LARGE" : "SENSITIVE_LITERAL";
    return base;
  }

  // ---- Fasi -----------------------------------------------------------------

  function baseReport(phase, provenance) {
    return {
      kind: "vidaa-install-v2",
      phase: phase,
      timestamp: new Date().toISOString(),
      collectionId: provenance.collectionId,
      clientBuildId: provenance.buildId,
      accessContext: {
        origin: location.origin,
        hostname: location.hostname,
        protocol: location.protocol,
        secureContext: !!window.isSecureContext
      },
      userAgent: String(navigator.userAgent || "").slice(0, 500),
      preferredContextObserved: location.hostname === "vidaahub.com"
    };
  }

  async function runProbe(provenance) {
    state.workingReader = null;
    state.workingWriter = null;
    state.beforeText = null;
    state.probeSaved = false;
    var report = baseReport("probe", provenance);
    report.capabilities = detectCapabilities();
    report.globalEnumeration = enumerateGlobals();
    report.readAttempts = [];

    var readers = makeReaders();
    for (var i = 0; i < readers.length && !state.workingReader; i++) {
      var reader = readers[i];
      for (var m = 0; m < READ_MODES.length; m++) {
        var attempt = { primitive: reader.name, path: APPINFO_PATH, mode: READ_MODES[m] };
        try {
          var res = reader.read(APPINFO_PATH, READ_MODES[m]);
          if (res.ok) {
            attempt.ok = true;
            attempt.bytes = utf8Length(res.text);
            attempt.sha256 = await sha256Text(res.text);
            try { attempt.entryCount = (JSON.parse(res.text).AppInfo || []).length; } catch (_) { attempt.entryCount = null; }
            state.workingReader = { name: reader.name + " mode " + READ_MODES[m], mode: READ_MODES[m], read: reader.read };
            state.beforeText = res.text;
          } else {
            attempt.ok = false;
            if (res.denied) attempt.denied = true;
            if (res.raw) attempt.detail = res.raw;
          }
        } catch (error) {
          attempt.ok = false;
          attempt.detail = "exception:" + short(error && error.message ? error.message : String(error));
        }
        report.readAttempts.push(attempt);
        if (state.workingReader) break;
      }
    }

    var writers = makeWriters();
    report.writePrimitivesPresent = writers.map(function (w) { return w.name; });
    report.identifierProvenance = identifierProvenance();
    report.pkgmgrObservation = pkgmgrObservation();
    report.outcome = state.workingReader
      ? (writers.length ? "READ_OK_WRITE_PRIMITIVE_PRESENT" : "READ_OK_NO_WRITE_PRIMITIVE")
      : (writers.length ? "READ_FAILED_WRITE_PRIMITIVE_PRESENT" : "NO_READ_NO_WRITE_PRIMITIVE");
    if (state.workingReader) report.registryBefore = registrySummary(state.beforeText);
    state.probeReport = report;
    report.limits = [
      "Sola lettura del registro, del canale pkgmgr e dei nomi; nessuna scrittura in questa fase.",
      "Presenza di una funzione non equivale a scrittura autorizzata.",
      "Contesto corrente della pagina; non copre altri processi o il firmware intero."
    ];
    return report;
  }

  async function attemptHiUtilsWrite(path, text, attempts) {
    var writers = makeWriters().filter(function (w) { return w.name === "HiUtils fileWrite"; });
    if (!writers.length) return false;
    var attempt = { primitive: "HiUtils fileWrite", phase: "write", path: path, mode: APPINFO_MODE };
    try {
      var res = writers[0].write(path, text, APPINFO_MODE);
      attempt.ok = res.ok;
      if (res.denied) attempt.denied = true;
      if (res.raw) attempt.detail = res.raw;
    } catch (error) {
      attempt.ok = false;
      attempt.detail = "exception:" + short(error && error.message ? error.message : String(error));
    }
    attempts.push(attempt);
    return attempt.ok === true;
  }

  function tryLegacyInstall(attempts) {
    return new Promise(function (resolve) {
      if (!has("Hisense_installApp")) return resolve(false);
      var callbackResult = "NO_CALLBACK_ENTRO_TIMEOUT";
      var returned;
      try {
        returned = Hisense_installApp(target.appId, target.appName, target.iconUrl, target.iconUrl,
          target.iconUrl, target.appUrl, target.storeType, function (res) {
          callbackResult = res;
        });
      } catch (error) {
        attempts.push({ primitive: "Hisense_installApp", phase: "call", ok: false, detail: "exception:" + short(String(error)) });
        return resolve(false);
      }
      setTimeout(function () {
        attempts.push({
          primitive: "Hisense_installApp",
          phase: "call",
          returnValue: String(returned),
          callbackValue: String(callbackResult),
          note: "callback 0 osservato in passato anche con installApplication 503: non e' prova. Vale solo il readback."
        });
        resolve(true);
      }, 1500);
    });
  }

  async function runInstall(provenance) {
    var report = baseReport("install", provenance);
    report.appEntry = buildEntry();
    report.attempts = [];

    // L'analisi deve essere stata salvata sul PC prima di qualsiasi scrittura.
    if (!state.probeSaved || !state.workingReader || !state.probeReport ||
        !state.probeReport.registryBefore || typeof state.probeReport.registryBefore.content !== "string") {
      report.outcome = "READ_UNAVAILABLE_NO_INSTALL";
      report.limits = ["Prima salva la fase Analizza: senza una copia valida del registro non si scrive."];
      return report;
    }

    // Rilettura immediata: se il registro è cambiato dopo il backup, si interrompe.
    var fresh;
    try { fresh = state.workingReader.read(APPINFO_PATH, state.workingReader.mode); }
    catch (error) {
      report.outcome = "READ_UNAVAILABLE_NO_INSTALL";
      report.attempts.push({ primitive: state.workingReader.name, phase: "prewrite-read",
        path: APPINFO_PATH, mode: state.workingReader.mode, ok: false,
        detail: "exception:" + short(error && error.message ? error.message : String(error)) });
      report.limits = ["La rilettura precedente alla scrittura non è riuscita: nessuna scrittura eseguita."];
      return report;
    }
    if (!fresh.ok || fresh.text !== state.beforeText) {
      report.outcome = "REGISTRY_CHANGED_SINCE_PROBE";
      report.attempts.push({ primitive: state.workingReader.name, phase: "prewrite-read",
        path: APPINFO_PATH, mode: state.workingReader.mode, ok: !!fresh.ok,
        contentChanged: !!(fresh.ok && fresh.text !== state.beforeText),
        detail: fresh.raw ? fresh.raw : "Il registro non coincide con il backup della fase Analizza." });
      report.limits = ["Nessuna scrittura eseguita. Ripeti Analizza per creare un backup aggiornato."];
      return report;
    }
    var beforeText = fresh.text;
    report.registryBefore = registrySummary(beforeText);
    var entryPresentBefore = false;
    try {
      entryPresentBefore = JSON.parse(beforeText).AppInfo.some(function (a) { return a && a.Id === target.appId; });
    } catch (_) {
      report.outcome = "READ_UNAVAILABLE_NO_INSTALL";
      report.limits = ["Il registro letto non è un AppInfo valido: nessuna scrittura eseguita."];
      return report;
    }
    var merged;
    try { merged = mergeRegistry(beforeText); }
    catch (error) {
      report.outcome = "READ_UNAVAILABLE_NO_INSTALL";
      report.limits = ["Merge non sicuro: " + short(error && error.message ? error.message : String(error))];
      return report;
    }
    report.merge = { countBefore: merged.countBefore, countAfter: merged.countAfter, entryPresentBefore: entryPresentBefore };

    // 2. Scrittura con la prima primitiva diretta disponibile (NON HiUtils).
    var directWriters = makeWriters().filter(function (w) { return w.name !== "HiUtils fileWrite"; });
    var writeOk = false;
    for (var i = 0; i < directWriters.length && !writeOk; i++) {
      var writer = directWriters[i];
      var wAttempt = { primitive: writer.name, phase: "write", path: APPINFO_PATH, mode: state.workingReader.mode };
      try {
        var wres = writer.write(APPINFO_PATH, merged.json, state.workingReader.mode);
        wAttempt.ok = wres.ok;
        if (wres.raw) wAttempt.detail = wres.raw;
        writeOk = wres.ok;
        if (writeOk) state.workingWriter = writer;
      } catch (error) {
        wAttempt.ok = false;
        wAttempt.detail = "exception:" + short(error && error.message ? error.message : String(error));
      }
      report.attempts.push(wAttempt);
    }

    // 3. HiUtils fileWrite: noto 503 su Q0707 (26 settembre). Registrato come
    //    dato aggiornato del firmware, non come strada attesa.
    if (!writeOk) {
      writeOk = await attemptHiUtilsWrite(APPINFO_PATH, merged.json, report.attempts);
    }

    // 4. Laboratorio identifier: baseline "" sul canale raw, poi i candidati
    //    osservati sulla TV. Se un candidato fa passare la scrittura il
    //    readback sotto lo verifica come per le altre primitive.
    var identifierLab = null;
    if (!writeOk) {
      identifierLab = await runIdentifierLab(APPINFO_PATH, merged.json, report.attempts);
      writeOk = identifierLab.writeSucceeded || identifierLab.registerSucceeded;
      report.identifierLab = identifierLab;
    }

    // 5. Canale pkgmgr: mai misurato su Q0707. Prima prova di canale con un
    //    nome pacchetto inesistente (atteso rifiuto senza effetti), poi un
    //    pacchetto reale gia' installato (nessun download previsto).
    var storeCalled = false;
    if (!writeOk) {
      await storeInstallPackage("sidee.probe.canale.inesistente", target.appId, report.attempts, "prova-canale");
      storeCalled = await storeInstallPackage("tv.vidaa.app.tvbrowser", target.appId, report.attempts, "pacchetto-esistente");
    }

    // 6. Registrazione legacy: solo se nessuna scrittura file e nessuna
    //    risposta pkgmgr. Il risultato vale solo se il readback la conferma.
    var legacyCalled = false;
    if (!writeOk && !storeCalled) {
      legacyCalled = await tryLegacyInstall(report.attempts);
    }

    // 7. Readback di verifica con lo stesso reader.
    //    La voce vale come installata solo se la scrittura e' riuscita, oppure
    //    il contenuto e' cambiato, oppure la voce non c'era prima: una voce
    //    preesistente con scrittura negata NON e' un'installazione verificata.
    var verifyAttempt = { primitive: state.workingReader.name, phase: "readback", path: APPINFO_PATH, mode: state.workingReader.mode };
    var verified = false, contentChanged = false;
    try {
      var rb = state.workingReader.read(APPINFO_PATH, state.workingReader.mode);
      if (rb.ok) {
        verifyAttempt.ok = true;
        verifyAttempt.bytes = utf8Length(rb.text);
        verifyAttempt.sha256 = await sha256Text(rb.text);
        report.registryAfter = registrySummary(rb.text);
        contentChanged = rb.text !== beforeText;
        try {
          var apps = JSON.parse(rb.text).AppInfo || [];
          verified = apps.some(function (a) { return a && a.Id === target.appId; });
          verifyAttempt.entryCount = apps.length;
          verifyAttempt.entryPresent = verified;
          verifyAttempt.contentChanged = contentChanged;
        } catch (_) { verifyAttempt.detail = "readback non JSON"; }
      } else {
        verifyAttempt.ok = false;
        if (rb.denied) verifyAttempt.denied = true;
        if (rb.raw) verifyAttempt.detail = rb.raw;
      }
    } catch (error) {
      verifyAttempt.ok = false;
      verifyAttempt.detail = "exception:" + short(error && error.message ? error.message : String(error));
    }
    report.attempts.push(verifyAttempt);

    if (verified && (writeOk || contentChanged || !entryPresentBefore)) {
      report.outcome = "REGISTRY_WRITE_VERIFIED_REBOOT_REQUIRED";
    } else if (verified) {
      report.outcome = "ENTRY_ALREADY_PRESENT_WRITE_NOT_VERIFIED";
    } else if (writeOk) report.outcome = "WRITE_OK_BUT_ENTRY_NOT_IN_READBACK";
    else if (legacyCalled) report.outcome = "ONLY_LEGACY_CALLED_UNVERIFIED";
    else if (storeCalled) report.outcome = "ONLY_PKG_REGISTER_CALLED_UNVERIFIED";
    else report.outcome = "ALL_WRITE_PATHS_FAILED";
    report.nextStep = verified
      ? "Riavvia la TV (spegnimento elettrico 30s). Il launcher legge Appinfo.json solo al boot. NON chiamare refreshAppsOnHisenseUI. Poi fase Verifica."
      : "Nessuna scrittura verificata: conservare questo report.";
    report.limits = [
      "Readback verifica il contenuto del registro, non la tile sul launcher: quella si vede solo dopo riavvio.",
      "Icona vuota sulla tile e' limite noto del firmware (cache icone popolata solo da install nativo).",
      "La registrazione punta a un URL: l'app resta dipendente da quell'origine."
    ];
    return report;
  }

  async function runVerify(provenance) {
    var report = baseReport("verify", provenance);
    report.attempts = [];
    if (!state.workingReader) {
      var probe = await runProbe(provenance);
      report.attempts = report.attempts.concat(probe.readAttempts.map(function (a) { a.phase = "read"; return a; }));
      report.capabilities = probe.capabilities;
    }
    if (!state.workingReader) {
      report.outcome = "READ_UNAVAILABLE";
      return report;
    }
    var attempt = { primitive: state.workingReader.name, phase: "verify-read", path: APPINFO_PATH, mode: state.workingReader.mode };
    try {
      var res = state.workingReader.read(APPINFO_PATH, state.workingReader.mode);
      if (res.ok) {
        attempt.ok = true;
        attempt.sha256 = await sha256Text(res.text);
        report.registryCurrent = registrySummary(res.text);
        var apps = JSON.parse(res.text).AppInfo || [];
        var present = apps.some(function (a) { return a && a.Id === target.appId; });
        attempt.entryCount = apps.length;
        attempt.entryPresent = present;
        report.outcome = present ? "ENTRY_PERSISTED" : "ENTRY_ABSENT_AFTER_REBOOT";
      } else {
        attempt.ok = false;
        if (res.raw) attempt.detail = res.raw;
        report.outcome = "READ_FAILED";
      }
    } catch (error) {
      attempt.ok = false;
      attempt.detail = "exception:" + short(error && error.message ? error.message : String(error));
      report.outcome = "READ_FAILED";
    }
    report.attempts.push(attempt);
    report.limits = ["La persistenza del registro non prova la tile: conferma visiva sul launcher dopo riavvio reale."];
    return report;
  }

  // ---- Invio al ricevitore --------------------------------------------------

  async function sendReport(report) {
    var response = await fetch("/snapshot", {
      method: "POST",
      redirect: "error",
      credentials: "omit",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(report)
    });
    if (!response.ok) throw new Error("Ricevitore HTTP " + response.status);
    return response.json();
  }

  function reportSaved(report, receipt, statusElement) {
    if (report.phase === "probe") state.probeSaved = true;
    statusElement.textContent = "Esito: " + report.outcome + ". Report salvato sul PC (ricevuta " + receipt.sha256.slice(0, 12) + "…).";
    if (report.phase === "probe" && (!report.registryBefore || typeof report.registryBefore.content !== "string")) {
      statusElement.textContent += " Installazione disabilitata: il backup completo del registro non è disponibile.";
    }
  }

  async function withManifest(runFn, statusEl) {
    var manifestResponse = await fetch("/manifest", { cache: "no-store", redirect: "error", credentials: "omit" });
    if (!manifestResponse.ok) throw new Error("Manifest indisponibile");
    var manifest = await manifestResponse.json();
    var script = document.getElementById("install-v2-script");
    var build = script ? new URL(script.src, location.href).searchParams.get("v") : null;
    if (build !== manifest.buildId) throw new Error("Pagina non aggiornata: ricarica prima di continuare");
    configureTarget(manifest.target);
    document.getElementById("target").textContent = "Voce: " + target.appName +
      " (Id " + target.appId + ") → " + target.appUrl;
    var report = await runFn(manifest);
    pending = report;
    var receipt = await sendReport(report);
    pending = null;
    reportSaved(report, receipt, statusEl);
    return report;
  }

  // ---- UI -------------------------------------------------------------------

  // Export per test off-TV (Node): nessuna UI, nessuna esecuzione automatica.
  if (typeof window === "undefined" && typeof module !== "undefined" && module.exports) {
    module.exports = { detectCapabilities, enumerateGlobals, makeReaders, makeWriters,
      mergeRegistry, buildEntry, registrySummary, runProbe, runInstall, runVerify,
      pkgmgrObservation, identifierProvenance, storeInstallPackage,
      _state: state, configureTarget: configureTarget, utf8Length: utf8Length, navigate: navigate };
    return;
  }
  if (typeof document === "undefined") return;

  var statusEl = document.getElementById("status");
  var probeBtn = document.getElementById("probe");
  var installBtn = document.getElementById("install");
  var verifyBtn = document.getElementById("verify");
  var retryBtn = document.getElementById("retry");
  var busy = false, pending = null;

  function canInstall() {
    return state.probeSaved && state.probeReport && state.probeReport.registryBefore &&
      typeof state.probeReport.registryBefore.content === "string";
  }
  function setBusy(value) {
    busy = value;
    probeBtn.disabled = value || !!pending;
    verifyBtn.disabled = value || !!pending;
    installBtn.disabled = value || !!pending || !canInstall();
    retryBtn.disabled = value || !pending;
    retryBtn.hidden = !pending;
  }

  document.getElementById("origin").textContent = location.origin +
    (location.hostname === "vidaahub.com" ? " — contesto vidaahub" : " — contesto diverso da vidaahub; risultato separato");
  document.getElementById("target").textContent = "Target Nuvio: caricato da config.json all'avvio della fase.";

  function guard(fn) {
    return function (event) {
      event.preventDefault();
      if (busy) return;
      setBusy(true);
      statusEl.textContent = "Operazione in corso…";
      return withManifest(fn, statusEl)
        .catch(function (error) {
          statusEl.textContent = "Operazione non riuscita: " + error.message;
          retryBtn.hidden = !pending;
        })
        .finally(function () {
          setBusy(false);
        });
    };
  }

  probeBtn.addEventListener("click", guard(runProbe));
  installBtn.addEventListener("click", guard(runInstall));
  verifyBtn.addEventListener("click", guard(runVerify));
  retryBtn.addEventListener("click", function (event) {
    event.preventDefault();
    if (busy || !pending) return;
    setBusy(true);
    var report = pending;
    return sendReport(report).then(function (receipt) {
      pending = null;
      retryBtn.hidden = true;
      reportSaved(report, receipt, statusEl);
    }).catch(function (error) {
      statusEl.textContent = "Invio non riuscito: " + error.message;
    }).finally(function () { setBusy(false); });
  });
  document.addEventListener("keydown", function (event) { navigate(event, document); });
  setBusy(false);

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { detectCapabilities: detectCapabilities, mergeRegistry: mergeRegistry, buildEntry: buildEntry };
  }
}());
