const assert = require("node:assert/strict");
const { collect, readSource } = require("../web/bridge-source-check.js");
const provenance = { collectionId: "test", buildId: "fixture" };
function body(text, status = 200) {
  const bytes = new TextEncoder().encode(text); let done = false;
  return { ok: status >= 200 && status < 300, status, body: { getReader: () => ({
    read: async () => done ? { done: true } : (done = true, { value: bytes, done: false }),
    cancel: async () => {}, releaseLock() {}
  }) } };
}
function root(scripts = [], timing = []) {
  const result = {
    location: { href: "http://vidaahub.com:8082/", origin: "http://vidaahub.com:8082", hostname: "vidaahub.com", protocol: "http:" },
    document: { scripts }, performance: { getEntriesByType: () => timing },
    navigator: { userAgent: "off-TV fixture" }, isSecureContext: false
  };
  for (const name of ["Hisense_installApp", "Hisense_FileRead", "HiUtils_createRequest", "vowOS", "vowOSContext", "clientInformation"])
    Object.defineProperty(result, name, { get() { throw new Error("Native access forbidden: " + name); } });
  return result;
}
(async () => {
  const calls = [];
  const report = await collect(root([{ src: "http://vidaahub.com:8082/bridge-source-check.js?v=fixture" }], [
    { initiatorType: "script", name: "https://tvmodules-vidaa.vidaahub.com/deviceapi/vidaatv.js" },
    { initiatorType: "fetch", name: "https://tvmodules-vidaa.vidaahub.com/private" },
    { initiatorType: "script", name: "https://tvmodules-vidaa.vidaahub.com/deviceapi/vidaatv.js" }
  ]), async (url, options) => {
    calls.push(url); assert.equal(options.credentials, "omit"); assert.equal(options.mode, "cors");
    assert.equal(options.redirect, "error"); return body("function example() { return true; }");
  }, provenance);
  assert.equal(calls.length, 1);
  assert.equal(report.sources[1].observedVia, "performance.resource");
  assert.equal(report.sources[1].status, "COMPLETE");
  assert.equal(report.preferredContextObserved, true);
  assert.equal(report.discovery.timingCount, 2);
  assert.equal((await collect(root(), () => { throw new Error("No fetch expected"); }, provenance)).outcome, "NO_NON_SIDEE_SCRIPT_OBSERVED");
  const privateUrls = ["https://u:p@tvmodules-vidaa.vidaahub.com/a.js", "https://tvmodules-vidaa.vidaahub.com/a.js?token=private"];
  const skipped = await collect(root(privateUrls.map(src => ({src}))), () => { throw new Error("Private fetch forbidden"); }, provenance);
  assert.ok(skipped.sources.every(item => item.status === "PRIVATE_URL_SKIPPED"));
  assert.ok(!JSON.stringify(skipped).includes("private"));
  const schemes = await collect(root([{src: "data:text/javascript,const token='private'"},
    {src: "file:///system/component.js"}]), () => { throw new Error("Non-HTTP fetch forbidden"); }, provenance);
  assert.ok(schemes.sources.every(item => item.status === "OUT_OF_SCOPE" && item.url === null));
  assert.ok(!JSON.stringify(schemes).includes("private"));
  assert.ok(!JSON.stringify(schemes).includes("system/component"));
  assert.equal((await readSource("fixture", async () => body("", 403), 20)).status, "DENIED");
  assert.equal((await readSource("fixture", async () => { throw new Error("CORS"); }, 20)).status, "UNAVAILABLE");
  const truncated = await readSource("fixture", async () => body("123456789"), 5);
  assert.equal(truncated.status, "TRUNCATED"); assert.equal(truncated.source, "12345"); assert.equal(truncated.complete, false);
  assert.equal((await readSource("fixture", async () => body(""), 20)).status, "EMPTY");
  const secret = await readSource("fixture", async () => body('const access_token = "secret-value";'), 100);
  assert.equal(secret.status, "SENSITIVE_SOURCE_OMITTED"); assert.ok(!secret.source);
  const native = root(); delete native.performance;
  const noTiming = await collect(native, () => { throw new Error("No fetch expected"); }, provenance);
  assert.equal(noTiming.discovery.timingStatus, "UNAVAILABLE");
  const limited = await collect(root(Array.from({length: 14}, (_, i) => ({src: "http://vidaahub.com:8082/test" + i + ".js"}))),
    async () => body("example"), provenance);
  assert.equal(limited.sources.filter(item => item.status === "COMPLETE").length, 12);
  assert.equal(limited.sources.filter(item => item.status === "NOT_COLLECTED_LIMIT").length, 2);
  console.log("Loaded-source fixtures passed; native API access forbidden.");
})().catch(error => { console.error(error); process.exitCode = 1; });
