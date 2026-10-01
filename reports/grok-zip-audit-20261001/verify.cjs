const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const esbuild = require('D:/nuvio/nuviotvsmart/node_modules/esbuild');

const root = __dirname;
const findings = [];

function loadModule(relative, imports = {}, globals = {}) {
  const source = fs.readFileSync(path.join(root, relative), 'utf8');
  const compiled = esbuild.transformSync(source, { loader: 'ts', format: 'cjs', target: 'es2022' }).code;
  const module = { exports: {} };
  const context = vm.createContext({
    module, exports: module.exports, structuredClone, URL,
    require(name) {
      if (!Object.prototype.hasOwnProperty.call(imports, name)) throw new Error('Unapproved module: ' + name);
      return imports[name];
    },
    ...globals,
  });
  new vm.Script(compiled, { filename: relative }).runInContext(context, { timeout: 1000 });
  return module.exports;
}

function simulatedEnvironment(userAgent = 'Offline audit; no TV') {
  const storage = new Map();
  const profile = loadModule('src/lib/vidaa/profile.ts');
  const bridge = loadModule('src/lib/vidaa/bridge.ts', {}, {
    window: { location: { href: 'https://audit.invalid/', origin: 'https://audit.invalid' } },
    navigator: { userAgent },
    sessionStorage: { setItem(k, v) { storage.set(k, v); }, getItem(k) { return storage.get(k) ?? null; } },
  });
  const install = loadModule('src/lib/vidaa/install.ts', { './profile': profile, './bridge': bridge });
  return { profile, bridge, install };
}

async function run() {
  {
    const { profile, install } = simulatedEnvironment();
    const first = await install.runFhdInstall(profile.DEFAULT_PROFILE, false);
    assert.equal(first.classification, 'REJECTED');
    findings.push({ scenario: 'Fresh desktop simulation, FHD off', classification: first.classification, verified: first.verified });
  }
  {
    const { profile, bridge, install } = simulatedEnvironment();
    assert.equal(bridge.isRealTv(), false);
    const first = await install.runFhdInstall(profile.DEFAULT_PROFILE, true);
    assert.equal(first.classification, 'VERIFIED INSTALLED');
    assert.equal(first.verified, true);
    findings.push({ scenario: 'Desktop simulation, FHD on; no TV present', classification: first.classification, verified: first.verified });
    const second = await install.runFhdInstall({ ...profile.DEFAULT_PROFILE, appId: 'second-app', appName: 'Second app', appUrl: 'https://second.invalid/' }, false);
    assert.equal(second.classification, 'VERIFIED INSTALLED');
    findings.push({ scenario: 'Desktop simulation, FHD off after previous FHD success', classification: second.classification, verified: second.verified });
  }
  {
    const { profile, bridge, install } = simulatedEnvironment('Hisense VIDAA TV browser (synthetic, offline)');
    assert.equal(bridge.isRealTv(), false);
    const result = await install.runFhdInstall(profile.DEFAULT_PROFILE, true);
    assert.equal(result.verified, true);
    findings.push({ scenario: 'Synthetic TV user agent with native wrappers absent', detectedRealTv: false, classification: result.classification, verified: result.verified });
  }
  {
    const profile = loadModule('src/lib/vidaa/profile.ts');
    const unrelated = { AppInfo: [{ Id: 'different-id', AppName: 'Nuvio TV', URL: 'https://different.invalid/' }] };
    const fake = {
      readAppInfo: () => ({ file: structuredClone(unrelated), raw: JSON.stringify(unrelated), error: null }),
      rememberBackup: () => {},
      writeAppInfo: () => ({ ret: true, msg: 'Mock success without changed readback' }),
      sendOmiUpdate: () => ({ ok: true, detail: 'Mock only' }),
      installAppLegacy: async () => ({ callback: 0, error: null }),
      loadBackup: () => null,
    };
    const install = loadModule('src/lib/vidaa/install.ts', { './profile': profile, './bridge': fake });
    const result = await install.runFhdInstall(profile.DEFAULT_PROFILE, true);
    assert.equal(result.verified, true);
    findings.push({ scenario: 'Mock readback has same name but different target ID and URL; requested entry absent', classification: result.classification, verified: result.verified });
  }
  {
    const profile = loadModule('src/lib/vidaa/profile.ts');
    const counts = { notifications: 0, legacyRequests: 0 };
    const fake = {
      readAppInfo: () => ({ file: { AppInfo: [] }, raw: '{"AppInfo":[]}', error: null }),
      rememberBackup: () => {},
      writeAppInfo: () => ({ ret: false, code: 503, msg: 'permission check appconfig' }),
      sendOmiUpdate: () => { counts.notifications++; return { ok: true, detail: 'Mock only' }; },
      installAppLegacy: async () => { counts.legacyRequests++; return { callback: 0, error: null }; },
      loadBackup: () => null,
    };
    const install = loadModule('src/lib/vidaa/install.ts', { './profile': profile, './bridge': fake });
    const result = await install.runFhdInstall(profile.DEFAULT_PROFILE, true);
    assert.equal(result.classification, 'REJECTED');
    assert.equal(result.verified, false);
    assert.equal(counts.notifications, 1);
    assert.equal(counts.legacyRequests, 1);
    findings.push({ scenario: 'Mock denied write and callback zero', classification: result.classification, verified: result.verified, subsequentCalls: counts });
  }
  {
    const bridge = loadModule('src/lib/vidaa/bridge.ts', {}, {
      window: { Hisense_installApp() {} }, navigator: {}, sessionStorage: {},
    });
    const result = await Promise.race([
      bridge.installAppLegacy({}).then(() => 'resolved'),
      new Promise(resolve => setTimeout(() => resolve('still pending'), 25)),
    ]);
    assert.equal(result, 'still pending');
    findings.push({ scenario: 'Mock API never invokes callback; source has no timeout', result });
  }
  {
    const handlers = new Map();
    const calls = { blue: 0, back: 0 };
    const hook = loadModule('src/components/tv/use-tv-keys.ts', {
      react: { useRef: current => ({ current }), useEffect: fn => fn() },
    }, {
      window: { addEventListener(k, fn) { handlers.set(k, fn); }, removeEventListener() {} },
    });
    hook.useTvKeys({ onBlue() { calls.blue++; }, onBack() { calls.back++; } });
    const ignored = [];
    for (const [key, code] of [['ArrowLeft', 37], ['ArrowUp', 38], ['ArrowRight', 39], ['ArrowDown', 40]]) {
      let handled = false;
      handlers.get('keydown')({ key, keyCode: code, target: { tagName: 'BUTTON' }, preventDefault() { handled = true; } });
      if (!handled) ignored.push(key);
    }
    for (const [key, code] of [['F9', 406], ['Escape', 461]]) {
      handlers.get('keydown')({ key, keyCode: code, target: { tagName: 'BUTTON' }, preventDefault() {} });
    }
    assert.equal(ignored.length, 4);
    assert.deepEqual(calls, { blue: 1, back: 1 });
    findings.push({ scenario: 'Keyboard handler exercised with synthetic events', directionalKeysIgnoredByHook: ignored, handledCalls: calls });
  }
  fs.writeFileSync(path.join(root, 'verification.json'), JSON.stringify({
    checkedOn: '2026-10-01 Europe/Rome',
    scope: 'Extracted source executed only in isolated JavaScript contexts with simulated or mocked APIs; no network or TV interaction',
    findings,
  }, null, 2) + '\n');
  process.stdout.write(JSON.stringify(findings, null, 2) + '\n');
}
run().catch(error => { process.stderr.write(String(error.stack || error)); process.exitCode = 1; });
