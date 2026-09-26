const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('web/hspdk-context.js', 'utf8');
let calls = 0;
const forbidden = () => { calls++; throw new Error('native method called'); };
const host = Object.create({ File: { read: forbidden, write: forbidden }, loadLibrary: forbidden });
const window = { Hisense: {}, HiBrowser: host, OtherObservedHost: host };
Object.defineProperty(window, 'UnknownGetter', { get: forbidden });
Object.defineProperty(window.Hisense, 'File', { get: forbidden });
window.observedWrapper = function () { return Hisense.File.read('launcher/Appinfo.json', 1); };
window.legacyLaunchWrapper = function (url) { return sendAM(':am,am,hi_browser:start=[hi_browser,-u,' + url + ']'); };
const context = vm.createContext({ window, location: { href: 'https://vidaahub.com/', origin: 'https://vidaahub.com' },
  navigator: { userAgent: 'test' }, document: { scripts: [] } });
vm.runInContext(source, context);
const result = window.SideeHspdkContext();
assert.equal(calls, 0);
assert.equal(result.version, 2);
assert.equal(result.exact[0].File.status, 'ACCESSOR_NOT_READ');
assert.equal(result.exact[1].callablePairObserved, true);
assert.equal(result.exact[1].File.ownerDepth, 1);
assert.equal(result.status, 'FILE_PAIR_OBSERVED_NOT_TESTED');
assert(result.discoveredSurfaces.some(s => s.path === 'window.OtherObservedHost'));
assert(result.sourceMatches.some(s => s.path === 'window.observedWrapper'));
assert(result.legacyLaunchContextMatches.some(s => s.path === 'window.legacyLaunchWrapper' && s.term.includes('hi_browser')));
assert(!result.sourceMatches.some(s => s.path === 'window.SideeHspdkContext'));
assert(!result.legacyLaunchContextMatches.some(s => s.path === 'window.SideeHspdkContext'));
delete window.HiBrowser;
delete window.OtherObservedHost;
const missing = window.SideeHspdkContext();
assert.equal(missing.exact[1].root.status, 'ABSENT');
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
