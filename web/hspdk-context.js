(function () {
  "use strict";
  // Descriptor-only discovery. Never execute a discovered native method or getter.
  var terms = /libhspdk-jsx\.so|(?:Hisense|HiBrowser)\.File|File\.(?:read|write)|launcher\/Appinfo\.json|websdk\/Appinfo\.json|loadLibrary/g;
  // Exact launch-context markers found in historical Hisense launcher source. Source-only detection; never launch them.
  var legacyLaunchTerms = /:am,am,(?:(?:hi_browser|lau_browser|tv_store):start|:start=\[(?:hi_browser|lau_browser|tv_store))|app_(?:hi_browser|lau_browser|tv_store)|amName\s*:\s*["']hi_browser["']|\/3rd\/internet_browser\/browser|\/3rd\/internet_browser\/apps\/|\/3rd_rw\/internet_browser\//g;
  var sensitive = /token|secret|password|cookie|credential|authorization|signature|certificate|nonce|session/i;
  function lookup(root, name) {
    for (var depth = 0; root && depth < 5; depth++) {
      try {
        var d = Object.getOwnPropertyDescriptor(root, name);
        if (d) return { descriptor: d, depth: depth };
        root = Object.getPrototypeOf(root);
      } catch (e) { return { error: String(e) }; }
    }
    return {};
  }
  function value(record) {
    var d = record.descriptor;
    return d && Object.prototype.hasOwnProperty.call(d, "value") ? d.value : undefined;
  }
  function meta(record) {
    var d = record.descriptor;
    if (!d) return { status: record.error ? "ERROR" : "ABSENT", error: record.error || null };
    var data = Object.prototype.hasOwnProperty.call(d, "value");
    return { status: data ? "DATA" : "ACCESSOR_NOT_READ", ownerDepth: record.depth,
      type: data ? (d.value === null ? "null" : typeof d.value) : "accessor",
      hasGetter: typeof d.get === "function", hasSetter: typeof d.set === "function" };
  }
  function object(v) { return v !== null && (typeof v === "object" || typeof v === "function"); }
  function shape(root) {
    var levels = [], seen = [];
    for (var depth = 0; object(root) && depth < 3 && seen.indexOf(root) < 0; depth++) {
      seen.push(root);
      try {
        var names = Object.getOwnPropertyNames(root).filter(function (n) { return !sensitive.test(n); });
        levels.push({ depth: depth, truncated: names.length > 80, properties: names.slice(0, 80).map(function (n) {
          return { name: n, descriptor: meta(lookup(root, n)) };
        }) });
        root = Object.getPrototypeOf(root);
      } catch (e) { levels.push({ error: String(e) }); break; }
    }
    return levels;
  }
  function surface(path, record) {
    var root = value(record), file = lookup(root, "File"), fileValue = value(file);
    var read = meta(lookup(fileValue, "read")), write = meta(lookup(fileValue, "write"));
    return { path: path, root: meta(record), properties: shape(root),
      loadLibrary: meta(lookup(root, "loadLibrary")), File: meta(file), read: read, write: write,
      callablePairObserved: read.type === "function" && write.type === "function" };
  }
  function capture() {
    var out = { version: 2, timestamp: new Date().toISOString(), readOnly: true,
      page: { href: location.href, origin: location.origin, userAgent: navigator.userAgent },
      exact: [], discoveredSurfaces: [], sourceMatches: [], legacyLaunchContextMatches: [], scripts: [],
      scannedGlobals: 0, scannedFunctions: 0, truncated: false,
      note: "Presence is not write permission. No getter, loader, file read/write or discovered function is invoked." };
    ["Hisense", "HiBrowser"].forEach(function (name) { out.exact.push(surface("window." + name, lookup(window, name))); });
    var seenFunctions = [], seenObjects = [], propertyBudget = 4000;
    function inspectFunction(fn, path) {
      if (typeof fn !== "function" || seenFunctions.indexOf(fn) >= 0 || path === "window.SideeHspdkContext") return;
      seenFunctions.push(fn); out.scannedFunctions++;
      try {
        var source = Function.prototype.toString.call(fn), bounded = source.slice(0, 24000);
        terms.lastIndex = 0;
        var match = terms.exec(bounded);
        if (match && out.sourceMatches.length < 40) out.sourceMatches.push({ path: path,
          term: match[0], sourceLength: source.length, truncated: source.length > 24000,
          excerpt: bounded.slice(Math.max(0, match.index - 300), match.index + 900) });
        legacyLaunchTerms.lastIndex = 0;
        var launchMatch = legacyLaunchTerms.exec(bounded);
        if (launchMatch && out.legacyLaunchContextMatches.length < 40) out.legacyLaunchContextMatches.push({
          path: path, term: launchMatch[0], sourceLength: source.length, truncated: source.length > 24000,
          excerpt: bounded.slice(Math.max(0, launchMatch.index - 300), launchMatch.index + 900),
          evidence: "HISTORICAL_LAUNCH_MARKER_ONLY"
        });
      } catch (e) { /* Some native functions do not expose source. */ }
    }
    try {
      var globals = Object.getOwnPropertyNames(window);
      out.truncated = globals.length > 1600;
      globals.slice(0, 1600).forEach(function (name) {
        if (sensitive.test(name) || name === "SideeHspdkContext") return;
        out.scannedGlobals++;
        var record = lookup(window, name), root = value(record), path = "window." + name;
        inspectFunction(root, path);
        if (!object(root) || root === window) return;
        if (lookup(root, "File").descriptor || lookup(root, "loadLibrary").descriptor) {
          if (out.discoveredSurfaces.length < 30) out.discoveredSurfaces.push(surface(path, record));
          else out.truncated = true;
        }
        if (seenObjects.indexOf(root) >= 0) return;
        seenObjects.push(root);
        if (propertyBudget <= 0) { out.truncated = true; return; }
        try {
          var names = Object.getOwnPropertyNames(root), limit = Math.min(100, propertyBudget);
          if (names.length > limit) out.truncated = true;
          names.slice(0, limit).forEach(function (key) {
            propertyBudget--;
            if (!sensitive.test(key)) inspectFunction(value(lookup(root, key)), path + "." + key);
          });
        } catch (e) { /* Enumeration failures do not stop the other surfaces. */ }
      });
    } catch (e) { out.error = String(e); }
    // Inventory only: no guessed system URLs and no execution/fetch of script sources.
    Array.prototype.slice.call(document.scripts || [], 0, 80).forEach(function (script, index) {
      out.scripts.push({ index: index, src: script.src || null, inline: !script.src,
        sideeOwned: script.hasAttribute("data-sidee") || /\/(?:app|hspdk-context)\.js(?:\?|$)/.test(script.src || "") });
    });
    out.status = out.exact.concat(out.discoveredSurfaces).some(function (s) { return s.callablePairObserved; })
      ? "FILE_PAIR_OBSERVED_NOT_TESTED" : "NO_FILE_PAIR_OBSERVED";
    return out;
  }
  window.SideeHspdkContext = capture;
})();
