const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('web/hspdk-context.js', 'utf8');
let calls = 0;
const forbidden = () => { calls++; throw new Error('native method called'); };
const host = Object.create({ File: { read: forbidden, write: forbidden }, loadLibrary: forbidden });
const window = {
  Hisense: {},
  HiBrowser: host,
  OtherObservedHost: host,
  modeljs: { sendam: forbidden },
  Hisense_TestRead: forbidden,
  HiUtils_probe: forbidden,
  vowOS: {
    service: { syncExecute: forbidden, getIdentifier: forbidden },
    store: { install: forbidden, open: forbidden, getApps: forbidden },
    tvinfo: { getParam: forbidden }
  },
  omi_platform: { inspectOnly: forbidden },
  opera_omi: { inspectOnly: forbidden },
  TvInfo_Json: { readOnlyValue: 1 }
};
Object.defineProperty(window, 'UnknownGetter', { get: forbidden });
Object.defineProperty(window.Hisense, 'File', { get: forbidden });
window.observedWrapper = function () { return Hisense.File.read('launcher/Appinfo.json', 1); };
window.legacyLaunchWrapper = function (url) { return sendAM(':am,am,hi_browser:start=[hi_browser,-u,' + url + ']'); };
window.legacyBrowserPathWrapper = function () { return '/3rd/internet_browser/browser'; };
window.sendAM = function (command) { return window.modeljs.sendam(command); };
window.asyncStartApp = function (pageId, command) { return sendAM(command); };
window.storeMetadataWrapper = function (appInfo) {
  return [appInfo.openMode, appInfo.unifiedAppName, appInfo.venderId, appInfo.mediaId,
    appInfo.configUrlDownload, appInfo.appBundle, appInfo.packaged, appInfo.hasDetailPage,
    appInfo.StoreType, appInfo.initialFrom].join('|');
};
window.StoreCatalogBridge = {
  getAppDetail: function (mediaId) { return { mediaId: mediaId, unifiedAppName: String(mediaId) }; },
  installKnown: function (appinfo) { return window.vowOS.store.installApp(appinfo, function () {}); }
};
window.storeMessageWrapper = function (appInfo) {
  var requestMsg = { type: 'APPMessage', MsgType: 'appControl', action: 'updateAppState',
    param: { event: 'AllAppsUpdate', appInfo: appInfo } };
  return window.omi_platform.sendPlatformMessage(JSON.stringify(requestMsg));
};
const context = vm.createContext({ window, location: { href: 'https://vidaahub.com/', origin: 'https://vidaahub.com' },
  navigator: { userAgent: 'test' }, document: { scripts: [] } });
vm.runInContext(source, context);
const result = window.SideeHspdkContext();
assert.equal(calls, 0);
assert.equal(result.version, 6);
assert.equal(result.vowOSNamespaces.store.descriptor.status, 'DATA');
assert(result.vowOSNamespaces.store.properties.some(p => p.name === 'install' && p.descriptor.type === 'function'));
assert(result.vowOSNamespaces.service.properties.some(p => p.name === 'syncExecute' && p.descriptor.type === 'function'));
assert(result.vowOSNamespaces.tvinfo.properties.some(p => p.name === 'getParam' && p.descriptor.type === 'function'));
assert.equal(result.vowOSNamespaces.store.invoked, false);
assert(result.modernBridgeInventory.globals.some(g => g.name === 'Hisense_TestRead' && g.descriptor.type === 'function'));
assert(result.modernBridgeInventory.globals.some(g => g.name === 'HiUtils_probe' && g.descriptor.type === 'function'));
assert.equal(result.modernBridgeInventory.objects.vowOS.descriptor.status, 'DATA');
assert.equal(result.modernBridgeInventory.objects.omi_platform.descriptor.status, 'DATA');
assert.equal(result.modernBridgeInventory.objects.opera_omi.descriptor.status, 'DATA');
assert.equal(result.modernBridgeInventory.objects.TvInfo_Json.descriptor.status, 'DATA');
assert.equal(result.modernBridgeInventory.invoked, false);
assert.equal(result.legacyAppManagerBridge.modeljs.status, 'DATA');
assert.equal(result.legacyAppManagerBridge.sendam.type, 'function');
assert.equal(result.legacyAppManagerBridge.callableObserved, true);
assert.equal(result.legacyAppManagerBridge.invoked, false);
assert(result.legacyAppManagerMatches.some(s => s.path === 'window.sendAM' && s.term === 'modeljs.sendam'));
assert.equal(result.exact[0].File.status, 'ACCESSOR_NOT_READ');
assert.equal(result.exact[1].callablePairObserved, true);
assert.equal(result.exact[1].File.ownerDepth, 1);
assert.equal(result.status, 'FILE_PAIR_OBSERVED_NOT_TESTED');
assert(result.discoveredSurfaces.some(s => s.path === 'window.OtherObservedHost'));
assert(result.sourceMatches.some(s => s.path === 'window.observedWrapper'));
assert(result.legacyLaunchContextMatches.some(s => s.path === 'window.legacyLaunchWrapper' && s.term.includes('hi_browser')));
assert(result.legacyLaunchContextMatches.some(s => s.path === 'window.legacyBrowserPathWrapper' && s.term === '/3rd/internet_browser/browser'));
assert(result.storeMetadataSourceMatches.some(s => s.path === 'window.storeMetadataWrapper' && s.term === 'openMode'));
assert(result.storeWorkflowSourceMatches.some(s => s.path === 'window.StoreCatalogBridge.getAppDetail' && s.term === 'getAppDetail'));
assert(result.omiMessageSourceMatches.some(s => s.path === 'window.storeMessageWrapper' && s.term === 'sendPlatformMessage'));
assert(result.storeRuntimeInventory.globals.some(g => g.name === 'StoreCatalogBridge'));
assert(result.storeRuntimeInventory.objects['window.StoreCatalogBridge'].properties.some(p => p.name === 'getAppDetail' && p.descriptor.type === 'function'));
assert.equal(result.storeRuntimeInventory.invoked, false);
assert(!result.sourceMatches.some(s => s.path === 'window.SideeHspdkContext'));
assert(!result.legacyLaunchContextMatches.some(s => s.path === 'window.SideeHspdkContext'));
delete window.HiBrowser;
delete window.OtherObservedHost;
delete window.modeljs;
delete window.sendAM;
delete window.asyncStartApp;
delete window.storeMetadataWrapper;
delete window.StoreCatalogBridge;
delete window.storeMessageWrapper;
delete window.Hisense_TestRead;
delete window.HiUtils_probe;
delete window.vowOS;
delete window.omi_platform;
delete window.opera_omi;
delete window.TvInfo_Json;
const missing = window.SideeHspdkContext();
assert.equal(missing.exact[1].root.status, 'ABSENT');
assert.equal(missing.legacyAppManagerBridge.modeljs.status, 'ABSENT');
assert.equal(missing.legacyAppManagerBridge.sendam.status, 'ABSENT');
assert.equal(missing.modernBridgeInventory.objects.vowOS.descriptor.status, 'ABSENT');
assert.equal(missing.vowOSNamespaces.store.descriptor.status, 'ABSENT');
assert.equal(missing.vowOSNamespaces.service.descriptor.status, 'ABSENT');
assert.equal(missing.vowOSNamespaces.tvinfo.descriptor.status, 'ABSENT');
assert.equal(missing.modernBridgeInventory.objects.omi_platform.descriptor.status, 'ABSENT');
assert.equal(missing.status, 'NO_FILE_PAIR_OBSERVED');
assert.equal(calls, 0);

// Run the actual generated bootstrap, not a copy of its logic.
if (process.argv[2]) {
  const html = fs.readFileSync(process.argv[2], 'utf8');
  const scripts = [...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1]);
  let payload;
  const elements = {};
  const bootstrapWindow = { HiUtils_createRequest: forbidden, Hisense: {} };
  class XHR {
    open(method, url) { assert.equal(method, 'POST'); assert.equal(url, '/api/app-context-bootstrap'); }
    setRequestHeader() {}
    send(body) { payload = JSON.parse(body); this.status = 200; this.readyState = 4;
      this.responseText = '{}'; this.onreadystatechange(); }
  }
  const bootstrap = vm.createContext({ window: bootstrapWindow, XMLHttpRequest: XHR,
    location: { href: 'http://vidaa.smartone-iptv.com/', origin: 'http://vidaa.smartone-iptv.com',
      hostname: 'vidaa.smartone-iptv.com', protocol: 'http:' }, navigator: { userAgent: 'test' },
    document: { scripts: [], getElementById(id) { return elements[id] ||= {}; } },
    setTimeout: forbidden });
  scripts.forEach(s => vm.runInContext(s, bootstrap));
  assert(payload.legacyHspdkContext.readOnly);
  assert.equal(payload.legacyHspdkContext.status, 'NO_FILE_PAIR_OBSERVED');
  assert.match(payload.clientBuildId, /^app-[a-f0-9]{12}$/);
  assert.equal(calls, 0);
}
console.log('HSPDK descriptor discovery and read-only bootstrap passed');
