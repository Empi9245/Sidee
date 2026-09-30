const assert = require("node:assert/strict");
const {snapshot} = require("../web/post-store-check.js");

// The API can return nested JSON text. Keep packaging metadata and redact URL
// credentials/query strings; do not retain unrelated account information.
const report = snapshot({
  location: {origin: "http://192.168.1.5:8080", protocol: "http:", hostname: "192.168.1.5"},
  isSecureContext: false,
  Hisense_getInstalledApps: () => JSON.stringify({ret: true, msg: JSON.stringify([
    {Id: "1876", AppName: "Duplecast", URL: "https://user:pass@example.invalid/ui?token=private",
      packaged: 0, cookie: "private", md5: "private"},
    {Id: "1", AppName: "Netflix", URL: "netflix"}
  ])}),
  vowOS: {store: {getInstalledPkgs: () => ({ret: true, msg: [
    {name: "tv.vidaa.app.tvbrowser", version: "1", path: "APPS:pkgs/tv.vidaa.app.tvbrowser/index.html"}
  ]})}}
});
assert.equal(report.apps.count, 2);
assert.equal(report.accessContext.origin, "http://192.168.1.5:8080");
assert.equal(report.accessContext.secureContext, false);
assert.equal(report.apps.targets.length, 1);
assert.equal(report.apps.targets[0].packaged, 0);
assert.equal(report.apps.targets[0].URL, "https://example.invalid/ui");
assert.ok(!JSON.stringify(report).includes("private"));
assert.equal(report.packages.count, 1);
assert.equal(report.packages.items[0].name, "tv.vidaa.app.tvbrowser");

const denied = snapshot({Hisense_getInstalledApps: () => ({ret: false, code: 503, msg: []})});
assert.equal(denied.apps.status, "DENIED");
assert.equal(denied.apps.count, null);
assert.equal(denied.packages.status, "UNAVAILABLE");
assert.equal(snapshot({Hisense_getInstalledApps: () => "not JSON"}).apps.status, "READ_ERROR");
assert.equal(snapshot({Hisense_getInstalledApps: () => ({unknown: []})}).apps.status, "UNRECOGNIZED_RESPONSE");
assert.equal(snapshot({}).apps.status, "UNAVAILABLE");
assert.equal(snapshot({}).accessContext.origin, null);
console.log("Post-Store inventory fixtures passed; no TV calls.");
