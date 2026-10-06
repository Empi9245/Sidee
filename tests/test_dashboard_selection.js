"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const html = fs.readFileSync(path.join(__dirname, "../core/dashboard.html"), "utf8");
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const defaultHelp = html.match(/<p id="tvname">([^<]+)<\/p>/)[1];

class Classes {
  constructor() { this.values = new Set(); }
  add(...names) { names.forEach(name => this.values.add(name)); }
  remove(...names) { names.forEach(name => this.values.delete(name)); }
  toggle(name, enabled) { enabled ? this.add(name) : this.remove(name); }
}

class Element {
  constructor(id = "") {
    this.id = id;
    this.textContent = id === "tvname" ? defaultHelp : "";
    this.value = "";
    this.hidden = true;
    this.disabled = ["btnInstall", "btnInstallStremio", "btnInstallJf", "btnRequest", "btnPair", "pin"].includes(id);
    this.classList = new Classes();
    this.dataset = {};
    this.attributes = {};
    this.children = [];
    this.subnodes = new Map();
  }
  querySelector(selector) {
    if (!this.subnodes.has(selector)) this.subnodes.set(selector, new Element());
    return this.subnodes.get(selector);
  }
  setAttribute(name, value) { this.attributes[name] = value; }
  removeAttribute(name) { delete this.attributes[name]; }
  replaceChildren(...children) { this.children = children; }
  append(child) { this.children.push(child); }
  focus() {}
  scrollIntoView() {}
}

async function dashboard(savedStatus, discoveryResults, phoneResponse) {
  const nodes = new Map();
  const node = id => {
    if (!nodes.has(id)) nodes.set(id, new Element(id));
    return nodes.get(id);
  };
  const requests = [];
  let discoveryIndex = 0;
  const context = vm.createContext({
    document: {getElementById: node, createElement: () => new Element(), body: new Element()},
    location: {search: "?key=fixture-key"},
    URLSearchParams,
    setTimeout: () => 1,
    clearTimeout: () => {},
    matchMedia: () => ({matches: true}),
    fetch: async address => {
      const url = new URL(address, "http://localhost");
      requests.push(url);
      let result;
      if (url.pathname === "/api/status") result = typeof savedStatus === "function" ? await savedStatus() : savedStatus;
      else if (url.pathname === "/api/discover") {
        result = discoveryResults[discoveryIndex++];
        if (result instanceof Error) throw result;
      } else if (url.pathname === "/api/phone") {
        result = phoneResponse ? await phoneResponse(url) : {ok: true, url: "http://10.23.7.5/?key=fixture-key", qr: "data:image/svg+xml;base64,fixture"};
      } else result = {ok: true};
      return {ok: true, json: async () => result};
    },
  });
  vm.runInContext(script, context);
  await new Promise(resolve => setImmediate(resolve));
  return {
    node,
    requests,
    find: async () => { await node("btnFind").onclick(); },
    choose: async host => { node("tvselect").value = host; await node("tvselect").onchange(); },
  };
}

const saved = host => ({paired: true, state: "ok", host, expires_at: Date.now() / 1000 + 86400});
const found = (...hosts) => ({ok: true, tvs: hosts.map((host, index) => ({host, friendly_name: "TV " + (index + 1)}))});

test("saved pairing does not preselect a TV before discovery", async () => {
  const app = await dashboard(saved("192.168.1.10"), []);
  assert.equal(app.node("tvname").textContent, defaultHelp);
  assert.equal(app.node("tvchip").textContent, "TV not connected");
  assert.equal(app.node("btnRequest").disabled, true);
  assert.equal(app.node("btnInstall").disabled, true);
  assert.equal(app.node("btnInstallStremio").disabled, true);
});

test("expired saved pairing also leaves the initial TV selection empty", async () => {
  const app = await dashboard({paired: true, state: "expired", host: "192.168.1.10", expires_at: 1}, []);
  assert.equal(app.node("tvname").textContent, defaultHelp);
  assert.equal(app.node("tvchip").textContent, "TV not connected");
});

test("discovery uses another network's actual TV IP", async () => {
  const app = await dashboard(saved("192.168.1.10"), [found("10.23.7.42")]);
  await app.find();
  assert.match(app.node("tvname").textContent, /10\.23\.7\.42/);
  assert.doesNotMatch(app.node("tvname").textContent, /192\.168\.1\.10/);
  assert.equal(app.node("btnRequest").disabled, false);
  assert.equal(app.node("btnInstall").disabled, true);
});

test("matching saved pairing is reused only after discovery", async () => {
  const app = await dashboard(saved("172.20.4.7"), [found("172.20.4.7")]);
  assert.equal(app.node("btnInstall").disabled, true);
  await app.find();
  assert.equal(app.node("btnInstall").disabled, false);
  assert.equal(app.node("btnInstallStremio").disabled, false);
  assert.match(app.node("tvchip").textContent, /Paired/);
});

test("selecting another TV does not reuse the first TV's saved pairing", async () => {
  const app = await dashboard(saved("172.20.4.7"), [found("172.20.4.7", "192.168.88.73")]);
  await app.find();
  assert.equal(app.node("btnInstall").disabled, false);
  await app.choose("192.168.88.73");
  assert.match(app.node("tvname").textContent, /192\.168\.88\.73/);
  assert.equal(app.node("btnInstall").disabled, true);
  assert.equal(app.node("btnRequest").disabled, false);
  assert.equal(app.node("tvchip").attributes.title, undefined);
});

test("an empty new search clears a previously selected TV", async () => {
  const app = await dashboard(saved("10.23.7.42"), [found("10.23.7.42"), found()]);
  await app.find();
  assert.equal(app.node("btnInstall").disabled, false);
  await app.find();
  assert.equal(app.node("tvname").textContent, defaultHelp);
  assert.equal(app.node("btnInstall").disabled, true);
  assert.equal(app.node("btnRequest").disabled, true);
  assert.equal(app.node("tvselect").children.length, 0);
});

test("a failed new search also disables operations on the stale TV", async () => {
  const app = await dashboard(saved("10.23.7.42"), [found("10.23.7.42"), new Error("Network unavailable")]);
  await app.find();
  await app.find();
  assert.equal(app.node("tvname").textContent, defaultHelp);
  assert.equal(app.node("btnInstall").disabled, true);
  assert.equal(app.node("btnRequest").disabled, true);
});

test("phone QR route follows each selected TV", async () => {
  const app = await dashboard(saved("192.168.1.10"), [found("10.23.7.42", "172.20.4.7")]);
  await app.find();
  await app.choose("172.20.4.7");
  const tvRoutes = app.requests.filter(url => url.pathname === "/api/phone" && url.searchParams.has("tv_host"));
  assert.deepEqual(tvRoutes.map(url => url.searchParams.get("tv_host")), ["10.23.7.42", "172.20.4.7"]);
});

test("a QR error on another TV hides the previous QR and link", async () => {
  const app = await dashboard(saved("10.23.7.42"), [found("10.23.7.42", "172.20.4.7")],
    url => url.searchParams.get("tv_host") === "172.20.4.7"
      ? {ok: false, error: "No route to this TV's network"}
      : {ok: true, url: "http://10.23.7.5/", qr: "data:current"});
  await app.find();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(app.node("phoneQr").hidden, false);
  await app.choose("172.20.4.7");
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(app.node("phoneQr").hidden, true);
  assert.equal(app.node("phoneLink").hidden, true);
  assert.equal(app.node("phoneMessage").hidden, false);
  assert.match(app.node("phoneMessage").textContent, /No route/);
});

test("a late initial QR response cannot overwrite the selected TV's QR", async () => {
  let finishInitialQR;
  const initialQR = new Promise(resolve => { finishInitialQR = resolve; });
  const app = await dashboard(saved("10.23.7.42"), [found("10.23.7.42")],
    url => url.searchParams.has("tv_host")
      ? {ok: true, url: "http://10.23.7.5/", qr: "data:current"} : initialQR);
  await app.find();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(app.node("phoneQr").src, "data:current");
  finishInitialQR({ok: true, url: "http://10.88.0.2/", qr: "data:stale"});
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(app.node("phoneQr").src, "data:current");
});

test("a late state error from another TV cannot disconnect the current selection", async () => {
  let failPreviousState;
  const previousState = new Promise((resolve, reject) => { failPreviousState = reject; });
  let statusCalls = 0;
  const app = await dashboard(() => ++statusCalls === 3 ? previousState : saved("172.20.4.7"),
    [found("172.20.4.7", "192.168.88.73")]);
  await app.find();
  const previousSelection = app.choose("192.168.88.73");
  await new Promise(resolve => setImmediate(resolve));
  await app.choose("172.20.4.7");
  assert.equal(app.node("btnInstall").disabled, false);
  failPreviousState(new Error("Old TV state request failed"));
  await previousSelection;
  assert.equal(app.node("btnInstall").disabled, false);
  assert.match(app.node("tvchip").textContent, /Paired/);
});

test("a late startup state error does not disconnect a TV found afterwards", async () => {
  let failStartupState;
  const startupState = new Promise((resolve, reject) => { failStartupState = reject; });
  let statusCalls = 0;
  const app = await dashboard(() => ++statusCalls === 1 ? startupState : saved("10.23.7.42"),
    [found("10.23.7.42")]);
  await app.find();
  assert.equal(app.node("btnInstall").disabled, false);
  failStartupState(new Error("Startup state request failed"));
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(app.node("btnInstall").disabled, false);
});
