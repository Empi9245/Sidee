(function () {
  "use strict";
  var session = Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 8);
  var markerKey = "sidee-nuvio-tv-marker-v1";
  var state = {
    kind: "nuvio-tv-observation-v1", session: session,
    userAgent: String(navigator.userAgent || "").slice(0, 120),
    secureContext: window.isSecureContext === true,
    installSignal: "NOT_OBSERVED", storageMarker: "NOT_CHECKED",
    navigation: [], errorCounts: {runtime: 0, rejectedPromise: 0, resource: 0}
  };
  var timer;
  var badge;
  var names = {ArrowUp: "UP", Up: "UP", ArrowDown: "DOWN", Down: "DOWN",
    ArrowLeft: "LEFT", Left: "LEFT", ArrowRight: "RIGHT", Right: "RIGHT",
    Enter: "OK", Return: "OK", BrowserBack: "BACK", GoBack: "BACK", Escape: "BACK"};
  var codes = {37: "LEFT", 38: "UP", 39: "RIGHT", 40: "DOWN", 13: "OK", 23: "OK",
    8: "BACK", 27: "BACK", 461: "BACK", 10009: "BACK"};

  function displayMode() {
    if (window.matchMedia) {
      if (window.matchMedia("(display-mode: standalone)").matches) return "standalone";
      if (window.matchMedia("(display-mode: fullscreen)").matches) return "fullscreen";
    }
    return "browser";
  }
  // Numbers below are UI hints only, not evidence that interaction succeeded.
  function uiState() {
    var active = document.activeElement;
    var focused = document.querySelector("#app .focused, #app .focus");
    var nodes = document.querySelectorAll("#app *");
    return {
      appRootPresent: !!document.getElementById("app"),
      screenCount: document.querySelectorAll("#app .screen").length,
      focusedCount: document.querySelectorAll("#app .focused, #app .focus").length,
      focusPosition: focused ? Array.prototype.indexOf.call(nodes, focused) : -1,
      activeTag: active && active.tagName || null
    };
  }
  function snapshot() {
    state.timestamp = new Date().toISOString();
    state.displayMode = displayMode();
    state.platform = String(window.__NUVIO_PLATFORM__ || "unrecorded").slice(0, 30);
    state.serviceWorkerApi = "serviceWorker" in navigator;
    state.serviceWorkerControlled = !!(navigator.serviceWorker && navigator.serviceWorker.controller);
    state.manifestPresent = !!document.querySelector('link[rel="manifest"]');
    state.ui = uiState();
    return state;
  }
  function send() {
    var body = JSON.stringify(snapshot());
    if (badge) badge.textContent = "Test TV · tasti " + state.navigation.length +
      " · installazione non attestata";
    fetch("/__sidee/observation", {method: "POST", headers: {"Content-Type": "application/json"},
      body: body, keepalive: true}).catch(function () {});
  }
  function schedule() {
    clearTimeout(timer);
    timer = setTimeout(send, 250);
  }
  try {
    var previous = localStorage.getItem(markerKey);
    localStorage.setItem(markerKey, previous || session);
    state.storageMarker = previous ? "PREVIOUS_MARKER_READ" : "NEW_MARKER_WRITTEN";
  } catch (_) { state.storageMarker = "UNAVAILABLE_OR_DENIED"; }

  document.addEventListener("keydown", function (event) {
    var tag = event.target && event.target.tagName;
    // Never record entry into account/search fields or arbitrary key values.
    if (tag === "INPUT" || tag === "TEXTAREA" || event.target && event.target.isContentEditable) return;
    var name = names[event.key] || names[event.keyName] || codes[event.keyCode || event.which];
    if (!name) return;
    var record = {action: name, code: Number(event.keyCode || event.which || 0),
      trusted: event.isTrusted === true, before: uiState()};
    state.navigation.push(record);
    state.navigation = state.navigation.slice(-24);
    setTimeout(function () { record.after = uiState(); schedule(); }, 20);
    // Observe Nuvio's own handlers; do not prevent keys or change its focus.
  }, true);
  window.addEventListener("beforeinstallprompt", function () {
    state.installSignal = "BROWSER_INSTALL_PROMPT_EVENT"; schedule();
  });
  window.addEventListener("appinstalled", function () {
    state.installSignal = "BROWSER_APPINSTALLED_EVENT"; schedule();
  });
  window.addEventListener("error", function (event) {
    if (event.target && event.target !== window) state.errorCounts.resource++;
    else state.errorCounts.runtime++;
    schedule();
  }, true);
  window.addEventListener("unhandledrejection", function () {
    state.errorCounts.rejectedPromise++; schedule();
  });
  window.addEventListener("pagehide", send);
  window.addEventListener("load", function () {
    badge = document.createElement("div");
    badge.style.cssText = "position:fixed;right:12px;bottom:12px;z-index:99999;" +
      "padding:6px 10px;background:#111;color:#fff;font:16px sans-serif;pointer-events:none";
    document.body.appendChild(badge);
    send();
    setTimeout(send, 2000);
    setTimeout(send, 6000);
  });
})();
