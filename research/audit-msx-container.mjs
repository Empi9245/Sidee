// Read-only, off-TV audit of the documented MSX BlobService implementation.
// Supply a downloaded public plugin file; no server or TV connection is opened.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';
import vm from 'node:vm';

const [sourcePath, receiptPath] = process.argv.slice(2);
if (!sourcePath || !receiptPath) {
  throw new Error('Usage: node audit-msx-container.mjs PLUGIN_SOURCE RECEIPT_JSON');
}
const source = await readFile(sourcePath, 'utf8');
const sha256 = createHash('sha256').update(source).digest('hex');
const reviewedSha256 = '7cf9daabeb7787094433f7958fed41d2bedc561496e987d01fc070c6a0183684';
assert.equal(sha256, reviewedSha256, 'Public source changed: inspect it before running this audit');
const start = source.indexOf('function r(){var P={};');
const end = source.indexOf('function w(', start);
assert.ok(start >= 0 && end > start, 'Reviewed BlobService body not found');
const blobServiceBody = source.slice(start, end);

const requests = [];
let storageAccesses = 0;
const syntheticResponse = Object.freeze({
  type: 'text/html',
  text: '<!doctype html><title>Owned test resource</title>',
});
const storage = new Proxy({}, {
  get() { storageAccesses++; throw new Error('Unexpected persistent-storage access'); },
  set() { storageAccesses++; throw new Error('Unexpected persistent-storage write'); },
});

function makeService() {
  const objectUrls = new Map();
  const urlApi = {
    createObjectURL(blob) {
      const url = `blob:synthetic-memory/${objectUrls.size + 1}`;
      objectUrls.set(url, blob);
      return url;
    },
    revokeObjectURL(url) { objectUrls.delete(url); },
  };
  class FakeXMLHttpRequest {
    open(method, url, async) {
      this.method = method;
      this.url = url;
      assert.equal(async, true);
    }
    setRequestHeader() {}
    send(data) {
      requests.push({ method: this.method, url: this.url, hasRequestBody: data != null });
      assert.equal(this.responseType, 'blob');
      this.response = syntheticResponse;
      this.readyState = 4;
      this.status = 200;
      this.onreadystatechange();
    }
  }
  const windowStub = { URL: urlApi, localStorage: storage, indexedDB: storage };
  const context = vm.createContext({
    e: windowStub,
    URL: urlApi,
    XMLHttpRequest: FakeXMLHttpRequest,
    a: { isFullStr: value => typeof value === 'string' && value.length > 0, strValue: String },
    A: { logger: { error: message => { throw new Error(message); } } },
  });
  new vm.Script(`${blobServiceBody}; this.service = new r();`).runInContext(context, { timeout: 1000 });
  return { service: context.service, objectUrls };
}

const first = makeService();
const ownedResourceUrl = 'https://example.invalid/owned-ui.html';
first.service.loadBlob('owned-ui', ownedResourceUrl, {});
assert.equal(requests[0].method, 'GET');
assert.equal(first.service.getBlob('owned-ui'), syntheticResponse);
assert.ok(first.service.getUrl('owned-ui').startsWith('blob:synthetic-memory/'));

first.service.executeBlob('owned-post', ownedResourceUrl, 'owned-input', {});
assert.equal(requests[1].method, 'POST');
assert.equal(requests[1].hasRequestBody, true);
assert.equal(first.service.getBlob('owned-post'), syntheticResponse);

const second = makeService();
assert.equal(second.service.getBlob('owned-ui'), null);
assert.equal(second.service.getUrl('owned-ui'), null);
assert.equal(second.service.getBlob('owned-post'), null);
assert.equal(requests.length, 2, 'Fresh service should not rehydrate or redownload entries');
assert.equal(storageAccesses, 0);
first.service.clear();
assert.equal(first.service.getBlob('owned-ui'), null);
assert.equal(first.objectUrls.size, 0);

const receipt = {
  auditDate: '2026-09-30',
  source: {
    url: 'https://msx.benzac.de/js/tvx-plugin.min.js',
    pluginVersion: '0.0.79',
    bytes: Buffer.byteLength(source),
    sha256,
  },
  scope: 'Reviewed BlobService only; mocked transport; no TV or browser execution',
  results: {
    loadBlobMethod: requests[0].method,
    executeBlobMethod: requests[1].method,
    responseKeptInCurrentInstance: true,
    freshRuntimeHasStoredResponse: false,
    freshRuntimeHasStoredObjectUrl: false,
    persistentStorageAccesses: storageAccesses,
    clearRevokesObjectUrls: true,
    realNetworkRequests: 0,
  },
  conclusion: 'This BlobService is transient response storage, not a persistent app importer.',
  limits: [
    'Does not prove the persistence behavior of the entire MSX app or its TV build.',
    'Does not exclude explicit persistence implemented separately by a plugin author.',
    'No launcher, remote, TV reboot, Nuvio UI or playback verification.',
  ],
};
await writeFile(receiptPath, `${JSON.stringify(receipt, null, 2)}\n`);
console.log(JSON.stringify(receipt.results));
