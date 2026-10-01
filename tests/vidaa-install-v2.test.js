const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const api = require("../web/vidaa-install-v2.js");
const target = {appId:"nuviodebug",appName:"Nuvio TV",
  appUrl:"http://192.168.1.5:4173/?wrapper=vidaa",
  iconUrl:"http://192.168.1.5:4173/assets/images/icon.png",storeType:"store"};
  const provenance = {collectionId:"fixture",buildId:"fixture-build",
    mode:"isolated-vidaa-install-v2",target:Object.assign({}, target, {identityMd5:"f31ae32083f6dc690241c46ad36b9526"})};

api.configureTarget(provenance.target);
const original = {Version:2,AppInfo:[{Id:"existing",AppName:"Existing"},{Id:"nuviodebug",AppName:"Old"}]};
const merged = JSON.parse(api.mergeRegistry(JSON.stringify(original)).json);
assert.equal(merged.Version, 2, "top-level registry fields must be preserved");
assert.deepEqual(merged.AppInfo.map(item => item.Id), ["existing", "nuviodebug"]);
assert.equal(merged.AppInfo[1].URL, target.appUrl);
assert.equal(api.buildEntry().StoreType, "store");
assert.throws(() => api.mergeRegistry("not json"));
assert.throws(() => api.mergeRegistry('{"Other":[]}'));
assert.equal(api.utf8Length("è"), 2);

function makeElement(tagName, disabled) {
  return {tagName,disabled:!!disabled,hidden:false,textContent:"",addEventListener(name, handler) { this[name] = handler; },
    getClientRects() { return [1]; },focus() { documentState.activeElement = this; },click() { this.clicked = true; }};
}
const documentState = {activeElement:null};

(async function () {
  let registry = JSON.stringify({Version:2,AppInfo:[{Id:"existing",AppName:"Existing"}]});
  const nativeCalls = {read:0,write:0};
  const reports = [];
  const requests = [];
  let failNextUpload = false;
  function read() { nativeCalls.read += 1; return registry; }
  function write(_path, text) { nativeCalls.write += 1; registry = text; return true; }

  const elements = {
    probe:makeElement("BUTTON"),install:makeElement("BUTTON",true),verify:makeElement("BUTTON"),
    retry:makeElement("BUTTON"),
    status:makeElement("P"),origin:makeElement("P"),target:makeElement("P")
  };
  elements.retry.hidden = true;
  const script = {src:"http://127.0.0.1:8084/vidaa-install-v2.js?v=fixture-build"};
  const doc = {currentScript:script,activeElement:elements.probe,
    getElementById(id) { return id === "install-v2-script" ? script : elements[id]; },
    addEventListener() {},querySelectorAll() { return [elements.probe,elements.install,elements.verify,elements.retry]; }};
  const root = {location:{origin:"http://127.0.0.1:8084",hostname:"127.0.0.1",protocol:"http:"},
    navigator:{userAgent:"VIDAA test"},isSecureContext:false,
    Hisense_FileRead:read,Hisense_FileWrite:write};
  async function fetcher(url, options) {
    requests.push({url,options});
    if (url === "/manifest") return {ok:true,json:async () => provenance};
    const report = JSON.parse(options.body);
    reports.push(report);
    if (failNextUpload) { failNextUpload = false; return {ok:false,status:503}; }
    return {ok:true,json:async () => ({sha256:"1234567890abcdef",phase:report.phase,outcome:report.outcome})};
  }
  const source = fs.readFileSync(path.join(__dirname, "../web/vidaa-install-v2.js"), "utf8");
  vm.runInNewContext(source, {window:root,document:doc,location:root.location,navigator:root.navigator,
    Hisense_FileRead:read,Hisense_FileWrite:write,fetch:fetcher,URL,TextEncoder,Promise,
    setTimeout,clearTimeout,console}, {timeout:2000});

  assert.equal(requests.length, 0, "page load must not trigger network or native operations");
  assert.deepEqual(nativeCalls, {read:0,write:0});
  await elements.probe.click({preventDefault() {}});
  assert.equal(nativeCalls.read, 1);
  assert.equal(nativeCalls.write, 0);
  assert.equal(reports[0].phase, "probe");
  assert.equal(reports[0].registryBefore.content, JSON.stringify({Version:2,AppInfo:[{Id:"existing",AppName:"Existing"}]}));
  assert.equal(elements.install.disabled, false, "saved backup enables installation");

  failNextUpload = true;
  await elements.install.click({preventDefault() {}});
  assert.equal(nativeCalls.write, 1, "installation requires the explicit second action");
  assert.equal(reports[1].phase, "install");
  assert.equal(reports[1].outcome, "REGISTRY_WRITE_VERIFIED_REBOOT_REQUIRED");
  assert.equal(elements.retry.hidden, false, "a failed upload retains the completed report");
  assert.equal(elements.probe.disabled, true, "a pending report blocks another operation");
  await elements.retry.click({preventDefault() {}});
  assert.equal(nativeCalls.write, 1, "retrying the report must not repeat the TV write");
  assert.deepEqual(reports[2], reports[1]);
  assert.equal(elements.retry.hidden, true);
  const installed = JSON.parse(registry);
  assert.equal(installed.Version, 2);
  assert.equal(installed.AppInfo.find(item => item.Id === target.appId).URL, target.appUrl);

  // Scenario 2: niente writer diretti, canale pkgmgr (vowOS.store) presente.
  // La prova-canale usa un pacchetto inesistente, poi quello reale gia'
  // installato; il mock risponde in due riprese come il wrapper reale.
  let registry2 = JSON.stringify({Version:2,AppInfo:[{Id:"existing",AppName:"Existing"}]});
  const pkgCalls = [];
  const read2 = () => registry2;
  const store = {
    getInstalledPkgs() { return {ret:true, msg:{items:[{name:"tv.vidaa.app.tvbrowser"},{name:"tv.vidaa.app.phoenix"}]}}; },
    installApp(payload, cb) {
      pkgCalls.push(payload);
      if (payload.packageName === "sidee.probe.canale.inesistente") {
        cb({ret:false, msg:{appId:payload.appId, message:"package not found"}});
      } else {
        cb(0); // callback interno di Hisense_installApp nel wrapper reale
        cb({ret:true, msg:{appId:payload.appId, message:"install ok"}});
      }
    }
  };
  const service = { getIdentifier() { return window.vowOSContext ? window.vowOSContext.getAppIdentifier() : ""; } };
  const elements2 = {
    probe:makeElement("BUTTON"),install:makeElement("BUTTON",true),verify:makeElement("BUTTON"),
    retry:makeElement("BUTTON"),status:makeElement("P"),origin:makeElement("P"),target:makeElement("P")
  };
  const doc2 = {currentScript:script,activeElement:elements2.probe,
    getElementById(id) { return id === "install-v2-script" ? script : elements2[id]; },
    addEventListener() {},querySelectorAll() { return [elements2.probe,elements2.install,elements2.verify,elements2.retry]; }};
  const root2 = {location:{origin:"https://vidaahub.com",hostname:"vidaahub.com",protocol:"https:"},
    navigator:{userAgent:"VIDAA test"},isSecureContext:true,Hisense_FileRead:read2,
    vowOS:{service, store}};
  const reports2 = [];
  async function fetcher2(url, options) {
    if (url === "/manifest") return {ok:true,json:async () => provenance};
    const report = JSON.parse(options.body);
    reports2.push(report);
    return {ok:true,json:async () => ({sha256:"1234567890abcdef",phase:report.phase,outcome:report.outcome})};
  }
  vm.runInNewContext(source, {window:root2,document:doc2,location:root2.location,navigator:root2.navigator,
    Hisense_FileRead:read2,vowOS:root2.vowOS,fetch:fetcher2,URL,TextEncoder,Promise,
    setTimeout,clearTimeout,console}, {timeout:8000});
  await elements2.probe.click({preventDefault() {}});
  assert.deepEqual(reports2[0].pkgmgrObservation.pkgNames, ["tv.vidaa.app.tvbrowser","tv.vidaa.app.phoenix"]);
  assert.match(reports2[0].identifierProvenance.getIdentifierSource, /vowOSContext/);
  assert.equal(elements2.install.disabled, false);
  await elements2.install.click({preventDefault() {}});
  assert.deepEqual(pkgCalls.map(call => call.packageName),
    ["sidee.probe.canale.inesistente", "tv.vidaa.app.tvbrowser"]);
  assert.equal(pkgCalls[1].appId, target.appId);
  assert.equal(pkgCalls[1].packageName, "tv.vidaa.app.tvbrowser", "il pacchetto reale usa pkgName, non un nome inventato");
  const installReport2 = reports2[1];
  assert.equal(installReport2.attempts.some(item => item.primitive === "pkgmgr prova-canale" && item.ok === false), true);
  assert.equal(installReport2.attempts.some(item => item.primitive === "pkgmgr pacchetto-esistente" && item.ok === true), true);
  assert.equal(installReport2.attempts.some(item => item.primitive === "Hisense_installApp"), false,
    "con risposta pkgmgr positiva il fallback legacy non parte");
  assert.equal(installReport2.outcome, "ONLY_PKG_REGISTER_CALLED_UNVERIFIED",
    "nessuna voce in Appinfo: il registro resta la sola verita'");
  assert.equal(JSON.parse(registry2).AppInfo.length, 1, "il mock pkgmgr non tocca Appinfo e il readback lo conferma");

  // Scenario 3: canale raw del bus con identifier controllabile. Nessun
  // writer diretto; il mock XMLHttpRequest accetta la scrittura solo con
  // l'identifier del pacchetto browser; baseline "" resta 503.
  let registry3 = JSON.stringify({Version:2,AppInfo:[{Id:"existing",AppName:"Existing"}]});
  const accepted = ["tv.vidaa.app.tvbrowser"];
  const read3 = () => registry3;
  const store3 = {
    getInstalledPkgs() { return {ret:true, msg:{items:[{name:"tv.vidaa.app.tvbrowser"},{name:"tv.vidaa.app.phoenix"}]}}; },
    installApp(payload, cb) { throw new Error("pkgmgr non deve partire se la scrittura identifier riesce"); }
  };
  const XMLHttpRequestMock = function () {
    const headers = {};
    const xhr = {
      open(method, url) { xhr.url = url; },
      setRequestHeader(name, value) { headers[name] = value; },
      send(body) {
        const parsed = JSON.parse(body);
        const identifier = headers.identifier || "";
        xhr.status = 200;
        if (parsed.api === "fileWrite" && accepted.indexOf(identifier) >= 0) {
          registry3 = parsed.args.writedata; // la "TV" accetta e scrive il registro
          xhr.responseText = JSON.stringify({ret:true, code:0, msg:"ok"});
        } else {
          xhr.responseText = JSON.stringify({ret:false, code:503,
            msg:"client request permission check error, please check appconfig"});
        }
      }
    };
    return xhr;
  };
  const elements3 = {
    probe:makeElement("BUTTON"),install:makeElement("BUTTON",true),verify:makeElement("BUTTON"),
    retry:makeElement("BUTTON"),status:makeElement("P"),origin:makeElement("P"),target:makeElement("P")
  };
  const doc3 = {currentScript:script,activeElement:elements3.probe,
    getElementById(id) { return id === "install-v2-script" ? script : elements3[id]; },
    addEventListener() {},querySelectorAll() { return [elements3.probe,elements3.install,elements3.verify,elements3.retry]; }};
  const root3 = {location:{origin:"https://vidaahub.com",hostname:"vidaahub.com",protocol:"https:"},
    navigator:{userAgent:"VIDAA test"},isSecureContext:true,Hisense_FileRead:read3,
    vowOS:{store:store3},XMLHttpRequest:XMLHttpRequestMock};
  const reports3 = [];
  async function fetcher3(url, options) {
    if (url === "/manifest") return {ok:true,json:async () => provenance};
    const report = JSON.parse(options.body);
    reports3.push(report);
    return {ok:true,json:async () => ({sha256:"1234567890abcdef",phase:report.phase,outcome:report.outcome})};
  }
  vm.runInNewContext(source, {window:root3,document:doc3,location:root3.location,navigator:root3.navigator,
    Hisense_FileRead:read3,vowOS:root3.vowOS,XMLHttpRequest:XMLHttpRequestMock,fetch:fetcher3,URL,TextEncoder,Promise,
    setTimeout,clearTimeout,console}, {timeout:8000});
  await elements3.probe.click({preventDefault() {}});
  await elements3.install.click({preventDefault() {}});
  const installReport3 = reports3[1];
  const lab = installReport3.identifierLab;
  assert.deepEqual(lab.identifiersTried, ["", "tv.vidaa.app.tvbrowser"],
    "baseline vuota, poi i candidati osservati; dopo il successo si ferma");
  assert.match(lab.baseline503, /appconfig/, "la baseline riproduce il 503 noto sullo stesso canale");
  const baselineAttempt = installReport3.attempts.find(item => item.primitive === "raw fileWrite identifier=<vuoto>");
  assert.equal(baselineAttempt.ok, false, "con identifier vuoto il mock risponde 503 come la TV reale");
  const successAttempt = installReport3.attempts.find(item => item.primitive === "raw fileWrite identifier=tv.vidaa.app.tvbrowser");
  assert.equal(successAttempt.ok, true);
  assert.equal(installReport3.attempts.some(item => item.primitive.startsWith("pkgmgr")), false,
    "nessuna sonda pkgmgr dopo una scrittura riuscita");
  assert.equal(installReport3.outcome, "REGISTRY_WRITE_VERIFIED_REBOOT_REQUIRED");
  const verified3 = JSON.parse(registry3);
  assert.equal(verified3.Version, 2, "il registro merge conserva i campi di primo livello");
  assert.equal(verified3.AppInfo.find(item => item.Id === target.appId).URL, target.appUrl);

  // Scenario 4: identita' nativa costruita assegnata con successo. Il mock
  // nativo deriva il token dall'JSON assegnato (come vowOSContext) e il
  // wrapper originale parte con quella identita': niente griglia raw.
  let registry4 = JSON.stringify({Version:2,AppInfo:[{Id:"existing",AppName:"Existing"}]});
  const read4 = () => registry4;
  const service4 = { getIdentifier() {
    const value = root4.navigator.appIdentifier;
    return typeof value === "string" && value.indexOf("nuviodebug") >= 0 ? "tok-native==" : "";
  } };
  const hiUtils4 = (type, msg) => {
    const value = root4.navigator.appIdentifier;
    if (type === "fileWrite" && typeof value === "string" && value.indexOf("nuviodebug") >= 0) {
      registry4 = msg.writedata;
      return {ret:true, code:0, msg:"ok"};
    }
    return {ret:false, code:503, msg:"client request permission check error, please check appconfig"};
  };
  const elements4 = {
    probe:makeElement("BUTTON"),install:makeElement("BUTTON",true),verify:makeElement("BUTTON"),
    retry:makeElement("BUTTON"),status:makeElement("P"),origin:makeElement("P"),target:makeElement("P")
  };
  const doc4 = {currentScript:script,activeElement:elements4.probe,
    getElementById(id) { return id === "install-v2-script" ? script : elements4[id]; },
    addEventListener() {},querySelectorAll() { return [elements4.probe,elements4.install,elements4.verify,elements4.retry]; }};
  const root4 = {location:{origin:"https://vidaa.duplecast.com",hostname:"vidaa.duplecast.com",protocol:"https:"},
    navigator:{userAgent:"VIDAA test"},isSecureContext:true,Hisense_FileRead:read4,
    HiUtils_createRequest:hiUtils4,vowOS:{service:service4}};
  const reports4 = [];
  async function fetcher4(url, options) {
    if (url === "/manifest") return {ok:true,json:async () => provenance};
    const report = JSON.parse(options.body);
    reports4.push(report);
    return {ok:true,json:async () => ({sha256:"1234567890abcdef",phase:report.phase,outcome:report.outcome})};
  }
  vm.runInNewContext(source, {window:root4,document:doc4,location:root4.location,navigator:root4.navigator,
    Hisense_FileRead:read4,HiUtils_createRequest:hiUtils4,vowOS:root4.vowOS,fetch:fetcher4,URL,TextEncoder,Promise,
    setTimeout,clearTimeout,console}, {timeout:8000});
  await elements4.probe.click({preventDefault() {}});
  await elements4.install.click({preventDefault() {}});
  const installReport4 = reports4[1];
  assert.equal(installReport4.accessContext.hostname, "vidaa.duplecast.com",
    "la pagina dichiara il contesto app in cui gira");
  const lab4 = installReport4.identifierLab;
  assert.equal(lab4.identityAssignment.assigned, true);
  assert.match(lab4.identityAssignment.identityJson, /"appid":"nuviodebug"/);
  assert.match(lab4.identityAssignment.identityJson, /f31ae32083f6dc690241c46ad36b9526/,
    "l'md5 dell'identita' arriva dal manifest (PC)");
  assert.equal(lab4.identityAssignment.identifierAfter, '"tok-native=="',
    "il layer nativo accetta l'identita' e produce il token di sessione");
  assert.deepEqual(lab4.identifiersTried, ["nativo-assegnato"],
    "con l'identita' nativa riuscita la griglia raw non parte");
  const nativeAttempt4 = installReport4.attempts.find(item => item.primitive === "HiUtils fileWrite (identita' nativa assegnata)");
  assert.equal(nativeAttempt4.ok, true);
  assert.equal(installReport4.outcome, "REGISTRY_WRITE_VERIFIED_REBOOT_REQUIRED");
  assert.equal(JSON.parse(registry4).AppInfo.find(item => item.Id === target.appId).Id, target.appId);

  const controls = [makeElement("BUTTON"),makeElement("BUTTON"),makeElement("BUTTON")];
  const navDoc = {activeElement:controls[0],querySelectorAll:() => controls};
  controls.forEach(control => { control.focus = function () { navDoc.activeElement = this; }; });
  api.navigate({key:"ArrowDown",preventDefault() {}}, navDoc);
  assert.equal(navDoc.activeElement, controls[1]);
  api.navigate({key:"Enter",preventDefault() {}}, navDoc);
  assert.equal(controls[1].clicked, true);
  console.log("VIDAA install v2: config target, safe merge, backup gate, explicit write and D-pad checks passed");
})().catch(error => { console.error(error); process.exitCode = 1; });
