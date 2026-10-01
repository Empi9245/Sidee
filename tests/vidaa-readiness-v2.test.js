const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const { makeReport, navigate } = require("../web/vidaa-readiness-v2.js");
const provenance = { collectionId: "fixture", buildId: "fixture-build", mode: "isolated-vidaa-readiness-v2", target: {appId:"test",appName:"Nuvio"} };
const source = fs.readFileSync(path.join(__dirname, "../web/vidaa-readiness-v2.js"), "utf8");

function browser(fetcher) {
  const ids = ["probe", "observe", "verify", "retry", "status", "origin", "target", "details", "reboot",
    "launcher", "remote", "persisted", "pcOff", "playback"];
  const elements = Object.fromEntries(ids.map(id => [id, { textContent:"", value:"unknown", hidden:id === "retry", disabled:false,
    checked:false, addEventListener(name, handler) { this[name] = handler; } }]));
  const script = {src:"http://127.0.0.1/vidaa-readiness-v2.js?v=fixture-build"};
  const doc = {currentScript:null,getElementById:id => id === "readiness-v2-script" ? script : elements[id],addEventListener() {}};
  const root = {location:{origin:"http://127.0.0.1"},navigator:{},isSecureContext:true};
  for (const name of ["Hisense_GetModelName", "Hisense_GetFirmWareVersion", "Hisense_GetOSVersion", "localStorage"])
    Object.defineProperty(root, name, {get() { throw new Error("Getter invocation forbidden"); }});
  const moduleShim = {exports:{}};
  vm.runInNewContext(source, {window:root,document:doc,location:root.location,module:moduleShim,URL,
    fetch:fetcher,AbortController,setTimeout,clearTimeout}, {timeout:1000});
  assert.deepEqual(moduleShim.exports, {});
  return {root,elements};
}
const event = {preventDefault() {}};

(async function () {
  const calls = [];
  const ui = browser(async (url, options) => {
    calls.push({url,options});
    assert.equal(options.redirect, "error"); assert.equal(options.credentials, "omit");
    if (url === "/manifest") return {ok:true,json:async () => provenance};
    if (calls.length === 2) throw new Error("Upload failed");
    return {ok:true,json:async () => ({outcome:"BROWSER_DESCRIPTORS_RECORDED"})};
  });
  assert.equal(calls.length, 0);
  const report = makeReport(ui.root, "probe", provenance);
  assert.equal(report.capabilities.localStorage, "accessor");
  assert.equal(report.capabilities.Hisense_GetModelName, "accessor");
  assert.equal(report.capabilities.Hisense_GetOSVersion, "accessor");
  await ui.elements.probe.click(event);
  assert.equal(ui.elements.retry.hidden, false);
  assert.equal(ui.elements.probe.disabled, false);
  await ui.elements.observe.click(event);
  assert.equal(calls.length, 2, "An unsent report must not be overwritten");
  await ui.elements.retry.click(event);
  assert.equal(calls[1].options.body, calls[2].options.body);
  assert.equal(ui.elements.retry.hidden, true);
  assert.match(ui.elements.status.textContent, /Nessuna installazione verificata/);
  await ui.elements.verify.click(event);
  assert.equal(calls.length, 3, "Post-reboot report requires explicit declaration");
  ui.elements.reboot.checked = true;
  await ui.elements.verify.click(event);
  assert.equal(JSON.parse(calls.at(-1).options.body).phase, "verify");
  assert.equal(JSON.parse(calls.at(-1).options.body).rebootConfirmed, true);
  const stale = browser(async () => ({ok:true,json:async () => ({...provenance,buildId:"old"})}));
  await stale.elements.probe.click(event);
  assert.match(stale.elements.status.textContent, /non aggiornata/);
  assert.equal(stale.elements.probe.disabled, false);
  const unavailable = browser(async () => { throw new Error("Receiver unavailable"); });
  await unavailable.elements.probe.click(event);
  assert.equal(unavailable.elements.retry.hidden, true);
  assert.equal(unavailable.elements.probe.disabled, false);
  const controls = ["BUTTON", "SELECT", "BUTTON"].map(tagName => ({tagName,hidden:false,disabled:false,
    getClientRects:() => [1],focus() { doc.activeElement = this; },click() { this.clicked = true; }}));
  controls[1].selectedIndex = 0; controls[1].options = [1,2,3];
  const doc = {activeElement:controls[0],querySelectorAll:() => controls};
  const press = (key, keyCode) => navigate({key,keyCode,preventDefault() {}}, doc);
  press("ArrowDown",40); assert.equal(doc.activeElement, controls[1]);
  press("ArrowRight",39); assert.equal(controls[1].selectedIndex,1);
  press("ArrowDown",40); assert.equal(doc.activeElement,controls[2]);
  press("Enter",13); assert.equal(controls[2].clicked,true);
  press("Escape",461); assert.equal(doc.activeElement,controls[0]);
  press(undefined,40); assert.equal(doc.activeElement,controls[1]);
  console.log("VIDAA v2: descriptor safety, explicit actions, stale-build rejection, retry retention and D-pad checks passed");
})().catch(error => { console.error(error); process.exitCode = 1; });
