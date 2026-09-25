(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const logBox = $("console");
  const state = {
    config: null,
    scan: null,
    permissionProbe: null,
    verification: null,
    installAttempts: [],
    startedAt: new Date().toISOString()
  };

  const KNOWN = [
    "Hisense_LoginWithVIDAA","Hisense_installApp_V2","Hisense_installApp",
    "Hisense_uninstallApp","Hisense_getInstalledApps","Hisense_GetApiVersion",
    "Hisense_GetDeviceInfo","Hisense_GetChromiumVersion","Hisense_GetCurrentBrowser",
    "Hisense_GetDeviceID","Hisense_GetFirmWareVersion","Hisense_GetDeviceCode",
    "Hisense_GetChipSetName","Hisense_GetOSVersion","Hisense_GetCountryCode",
    "Hisense_GetRegion","Hisense_GetPanelResolution","Hisense_GetIPAddress",
    "Hisense_GetFeatureCode","Hisense_GetCapabilityCode","Hisense_GetBrand",
    "Hisense_GetModelName","Hisense_GetTestApiList","Hisense_SupportAppConfig",
    "Hisense_GetDNS","Hisense_GetMacAddress","Hisense_FileRead","Hisense_FileWrite",
    "Hisense_HiSdkSignCreate","Hisense_HiSdkSignCreateSoundbar","Hisense_HiSdkJsonVerifyHeap",
    "Hisense_CheckAccessCode","Hisense_CheckCodeValid","Hisense_GetRoleID","Hisense_SetRoleID",
    "Hisense_GetCustomerID","Hisense_SetCustomerID","Hisense_Encrypt","Hisense_Decrypt",
    "Hisense_RSADecrypt","HiUtils_createRequest","vowOS","omi_platform","opera_omi"
  ];

  const SAFE_GETTERS = [
    "Hisense_GetApiVersion","Hisense_GetDeviceInfo","Hisense_GetChromiumVersion",
    "Hisense_GetCurrentBrowser","Hisense_GetFirmWareVersion","Hisense_GetDeviceCode",
    "Hisense_GetChipSetName","Hisense_GetOSVersion","Hisense_GetCountryCode",
    "Hisense_GetRegion","Hisense_GetPanelResolution","Hisense_GetIPAddress",
    "Hisense_GetFeatureCode","Hisense_GetCapabilityCode","Hisense_GetBrand",
    "Hisense_GetModelName","Hisense_GetTestApiList"
  ];

  const PROBE_LIMITS = Object.freeze({
    maxDepth: 3,
    maxPropertiesPerObject: 80,
    maxEntries: 700,
    maxEntriesPerRoot: 220,
    maxStringLength: 1000,
    maxFunctionSourceLength: 5000,
    maxGlobalMatches: 320,
    maxPrototypeProperties: 50,
    maxSourceReferences: 50
  });

  const PERMISSION_PROBE_MATCHER = /(hisense|vidaa|hiutils|vowos|omi|install(application)?|uninstall|appinfo|appconfig|permission(s)?|access|client|whitelist|domain|origin|security|config|capabilit(y|ies)|privilege|auth|certificate|signature|sign|file(read|write)|debug|api(version|list)|platform)/i;
  const SOURCE_REFERENCE_MATCHER = /(appconfig|permission|access|client|whitelist|domain|origin|security|installapplication|config|capabilit|privilege|auth|certificate|signature|sign|vowos|hiutils|syncexecute|service|role|customer|encrypt|decrypt|rsa|api|args)/i;

  const INSPECT_ONLY_SECURITY_APIS = [
    "Hisense_HiSdkSignCreate",
    "Hisense_HiSdkSignCreateSoundbar",
    "Hisense_HiSdkJsonVerifyHeap",
    "Hisense_CheckAccessCode",
    "Hisense_CheckCodeValid",
    "Hisense_GetRoleID",
    "Hisense_SetRoleID",
    "Hisense_GetCustomerID",
    "Hisense_SetCustomerID",
    "Hisense_Encrypt",
    "Hisense_Decrypt",
    "Hisense_RSADecrypt"
  ];

  function errorText(error) {
    return String(error && error.message || error);
  }

  function truncateText(value, limit) {
    const text = String(value);
    return text.length > limit ? text.slice(0, limit) + "…[truncated]" : text;
  }

  function isPrimitiveValue(value) {
    return value === null || ["undefined","string","number","boolean","bigint","symbol"].includes(typeof value);
  }

  function snapshotPrimitive(value) {
    if (value === undefined) return "[undefined]";
    if (typeof value === "bigint") return String(value) + "n";
    if (typeof value === "symbol") return truncateText(String(value), PROBE_LIMITS.maxStringLength);
    if (typeof value === "string") return truncateText(value, PROBE_LIMITS.maxStringLength);
    return value;
  }

  function safeFunctionSource(fn) {
    if (typeof fn !== "function") return null;
    try {
      return truncateText(Function.prototype.toString.call(fn), PROBE_LIMITS.maxFunctionSourceLength);
    } catch (error) {
      return "[source unavailable: " + errorText(error) + "]";
    }
  }

  function extractInterestingReferences(source) {
    if (!source) return [];
    const found = [];
    const seen = new Set();
    const add = (value) => {
      const text = truncateText(value, 180);
      if (!text || seen.has(text) || !SOURCE_REFERENCE_MATCHER.test(text)) return;
      seen.add(text);
      found.push(text);
    };
    try {
      (source.match(/[A-Za-z_$][A-Za-z0-9_$.-]{1,120}/g) || []).forEach(add);
      (source.match(/["'][^"'\\n]{1,160}["']/g) || []).forEach((quoted) => add(quoted.slice(1, -1)));
    } catch (_) {}
    return found.slice(0, PROBE_LIMITS.maxSourceReferences);
  }

  function descriptorSnapshot(descriptor) {
    if (!descriptor) return null;
    const snapshot = {
      enumerable: Boolean(descriptor.enumerable),
      configurable: Boolean(descriptor.configurable),
      hasGetter: typeof descriptor.get === "function",
      hasSetter: typeof descriptor.set === "function"
    };
    if (Object.prototype.hasOwnProperty.call(descriptor, "writable")) {
      snapshot.writable = Boolean(descriptor.writable);
    }
    if (typeof descriptor.get === "function") snapshot.getterSource = safeFunctionSource(descriptor.get);
    if (typeof descriptor.set === "function") snapshot.setterSource = safeFunctionSource(descriptor.set);
    return snapshot;
  }

  function safePrototypeInfo(value) {
    if (value === null || !["object","function"].includes(typeof value)) return null;
    try {
      const prototype = Object.getPrototypeOf(value);
      if (!prototype) return {isNull:true, ownProperties:[]};
      let names = [];
      try { names = Object.getOwnPropertyNames(prototype); } catch (error) {
        return {isNull:false, error:errorText(error), ownProperties:[]};
      }
      let constructorName = null;
      try {
        const ctorDescriptor = Object.getOwnPropertyDescriptor(prototype, "constructor");
        if (ctorDescriptor && typeof ctorDescriptor.value === "function") {
          const nameDescriptor = Object.getOwnPropertyDescriptor(ctorDescriptor.value, "name");
          if (nameDescriptor && typeof nameDescriptor.value === "string") {
            constructorName = truncateText(nameDescriptor.value, 120);
          }
        }
      } catch (_) {}
      return {
        isNull:false,
        constructorName,
        ownPropertyCount:names.length,
        ownProperties:names.slice(0, PROBE_LIMITS.maxPrototypeProperties)
      };
    } catch (error) {
      return {error:errorText(error), ownProperties:[]};
    }
  }

  function findPropertyDescriptor(root, name, maxDepth) {
    let cursor = root;
    for (let depth = 0; cursor && depth <= maxDepth; depth++) {
      try {
        const descriptor = Object.getOwnPropertyDescriptor(cursor, name);
        if (descriptor) return {descriptor, ownerDepth:depth};
        cursor = Object.getPrototypeOf(cursor);
      } catch (error) {
        return {error:errorText(error), ownerDepth:depth};
      }
    }
    return null;
  }

  function inspectGlobal(name) {
    const path = "window." + name;
    const found = findPropertyDescriptor(window, name, 4);
    if (!found) {
      return {name, path, propertyName:name, available:false, type:"missing"};
    }
    if (found.error) {
      return {name, path, propertyName:name, available:false, type:"blocked", error:found.error, ownerDepth:found.ownerDepth};
    }

    const descriptor = found.descriptor;
    const record = {
      name,
      path,
      propertyName:name,
      available:true,
      ownerDepth:found.ownerDepth,
      descriptor:descriptorSnapshot(descriptor)
    };

    if (!Object.prototype.hasOwnProperty.call(descriptor, "value")) {
      record.type = "accessor";
      record.access = "not invoked";
      return record;
    }

    const value = descriptor.value;
    record.type = value === null ? "null" : typeof value;
    if (isPrimitiveValue(value)) record.primitiveValue = snapshotPrimitive(value);
    if (typeof value === "function") {
      record.source = safeFunctionSource(value);
      record.sourceReferences = extractInterestingReferences(record.source);
    }
    if (value !== null && ["object","function"].includes(typeof value)) {
      record.prototype = safePrototypeInfo(value);
    }
    return record;
  }

  function getGlobalDataValue(name) {
    const found = findPropertyDescriptor(window, name, 4);
    if (!found || found.error) return {found:Boolean(found), error:found && found.error || null, data:false};
    const descriptor = found.descriptor;
    if (!Object.prototype.hasOwnProperty.call(descriptor, "value")) {
      return {found:true, data:false, accessor:true, descriptor};
    }
    return {found:true, data:true, value:descriptor.value, descriptor};
  }

  function createProbeBudget() {
    return {
      entries:0,
      limitReached:false,
      seen:typeof WeakSet === "function" ? new WeakSet() : []
    };
  }

  function wasSeen(budget, value) {
    if (value === null || !["object","function"].includes(typeof value)) return false;
    if (budget.seen instanceof WeakSet) {
      if (budget.seen.has(value)) return true;
      budget.seen.add(value);
      return false;
    }
    if (budget.seen.indexOf(value) >= 0) return true;
    budget.seen.push(value);
    return false;
  }

  function propertyPath(base, propertyName) {
    return /^[A-Za-z_$][A-Za-z0-9_$]*$/.test(propertyName)
      ? base + "." + propertyName
      : base + "[" + JSON.stringify(propertyName) + "]";
  }

  function inspectObjectTree(rootValue, rootPath, budget) {
    const result = {
      rootPath,
      objects:[],
      entries:[],
      circularPaths:[],
      errors:[],
      truncated:false
    };
    if (rootValue === null || !["object","function"].includes(typeof rootValue)) return result;

    const queue = [{value:rootValue,path:rootPath,depth:0}];
    let rootEntries = 0;

    while (queue.length) {
      if (budget.entries >= PROBE_LIMITS.maxEntries || rootEntries >= PROBE_LIMITS.maxEntriesPerRoot) {
        budget.limitReached = true;
        result.truncated = true;
        break;
      }

      const current = queue.shift();
      if (wasSeen(budget, current.value)) {
        result.circularPaths.push(current.path);
        continue;
      }

      let propertyNames;
      try {
        propertyNames = Object.getOwnPropertyNames(current.value);
      } catch (error) {
        result.errors.push({path:current.path,error:errorText(error)});
        continue;
      }

      const interesting = propertyNames.filter((name) => PERMISSION_PROBE_MATCHER.test(name) || name === "service");
      const interestingSet = new Set(interesting);
      const ordered = interesting.concat(propertyNames.filter((name) => !interestingSet.has(name)));
      const selected = ordered.slice(0, PROBE_LIMITS.maxPropertiesPerObject);

      result.objects.push({
        path:current.path,
        depth:current.depth,
        propertyCount:propertyNames.length,
        scannedPropertyCount:selected.length,
        interestingProperties:interesting.slice(0, PROBE_LIMITS.maxPropertiesPerObject),
        propertiesTruncated:propertyNames.length > selected.length,
        prototype:safePrototypeInfo(current.value)
      });

      for (const propertyName of selected) {
        if (budget.entries >= PROBE_LIMITS.maxEntries || rootEntries >= PROBE_LIMITS.maxEntriesPerRoot) {
          budget.limitReached = true;
          result.truncated = true;
          break;
        }

        const entry = {
          path:propertyPath(current.path, propertyName),
          propertyName,
          depth:current.depth + 1
        };
        let descriptor;
        try {
          descriptor = Object.getOwnPropertyDescriptor(current.value, propertyName);
        } catch (error) {
          entry.type = "blocked";
          entry.error = errorText(error);
          result.entries.push(entry);
          budget.entries += 1;
          rootEntries += 1;
          continue;
        }

        if (!descriptor) {
          entry.type = "missing-descriptor";
          result.entries.push(entry);
          budget.entries += 1;
          rootEntries += 1;
          continue;
        }

        entry.descriptor = descriptorSnapshot(descriptor);

        if (!Object.prototype.hasOwnProperty.call(descriptor, "value")) {
          entry.type = "accessor";
          entry.access = "not invoked";
        } else {
          const value = descriptor.value;
          entry.type = value === null ? "null" : typeof value;
          if (isPrimitiveValue(value)) entry.primitiveValue = snapshotPrimitive(value);
          if (typeof value === "function") {
            entry.source = safeFunctionSource(value);
            entry.sourceReferences = extractInterestingReferences(entry.source);
          }
          if (value !== null && ["object","function"].includes(typeof value)) {
            entry.prototype = safePrototypeInfo(value);
            if (current.depth < PROBE_LIMITS.maxDepth) {
              queue.push({value,path:entry.path,depth:current.depth + 1});
            }
          }
        }

        result.entries.push(entry);
        budget.entries += 1;
        rootEntries += 1;
      }
    }

    return result;
  }

  function analyzeNamedFunction(name) {
    const globalRecord = inspectGlobal(name);
    return {
      name,
      present:globalRecord.available,
      type:globalRecord.type,
      descriptor:globalRecord.descriptor || null,
      source:globalRecord.source || null,
      sourceReferences:globalRecord.sourceReferences || [],
      called:false,
      error:globalRecord.error || null
    };
  }

  function probeSupportAppConfig(budget) {
    const globalRecord = inspectGlobal("Hisense_SupportAppConfig");
    const result = {
      name:"Hisense_SupportAppConfig",
      present:globalRecord.available,
      type:globalRecord.type,
      descriptor:globalRecord.descriptor || null,
      source:globalRecord.source || null,
      sourceReferences:globalRecord.sourceReferences || [],
      called:false,
      status:globalRecord.available ? "present" : "unavailable"
    };

    if (!globalRecord.available) return result;

    const dataValue = getGlobalDataValue("Hisense_SupportAppConfig");
    if (!dataValue.data) {
      result.status = dataValue.accessor ? "accessor-not-invoked" : "unavailable";
      if (dataValue.error) result.error = dataValue.error;
      return result;
    }
    if (typeof dataValue.value !== "function") {
      result.status = "not-a-function";
      return result;
    }

    result.called = true;
    try {
      const value = dataValue.value();
      result.status = "returned";
      result.resultType = value === null ? "null" : typeof value;
      if (isPrimitiveValue(value)) {
        result.resultValue = snapshotPrimitive(value);
      } else {
        result.resultInspection = inspectObjectTree(value, "Hisense_SupportAppConfig()", budget);
      }
    } catch (error) {
      result.status = "error";
      result.error = errorText(error);
    }
    return result;
  }

  function log(message, data) {
    const line = "[" + new Date().toLocaleTimeString() + "] " + message;
    logBox.textContent += line + (data === undefined ? "" : "\n" + safeJson(data)) + "\n";
    logBox.scrollTop = logBox.scrollHeight;
  }

  function safeJson(value) {
    try { return JSON.stringify(value, null, 2); } catch (_) { return String(value); }
  }

  function safeValue(value) {
    if (value == null || ["string","number","boolean"].includes(typeof value)) return value;
    if (typeof value === "function") return "[function]";
    try { return JSON.parse(JSON.stringify(value)); } catch (_) { return String(value); }
  }

  function setInstallState(text, type) {
    const el = $("installState");
    el.textContent = text;
    el.className = "state" + (type ? " " + type : "");
  }

  async function getConfig() {
    const r = await fetch("/api/config", {cache:"no-store"});
    state.config = await r.json();
    const app = state.config.nuvio || {};
    $("appId").value = app.app_id || "nuviodebug";
    $("appName").value = app.app_name || "Nuvio TV";
    $("appUrl").value = app.app_url || "";
    $("iconUrl").value = app.icon_url || "";
  }

  function resolveIconUrl(target) {
    const raw = (target.icon_url || "").trim();
    if (raw && raw !== target.app_url) return raw;
    try {
      const url = new URL(target.app_url);
      return url.origin + "/assets/images/icon.png";
    } catch (_) {
      return raw;
    }
  }

  function currentTarget() {
    const target = {
      app_id: $("appId").value.trim(),
      app_name: $("appName").value.trim(),
      app_url: $("appUrl").value.trim(),
      icon_url: $("iconUrl").value.trim(),
      store_type: state.config?.nuvio?.store_type || "store"
    };
    if (!target.icon_url || target.icon_url === target.app_url) {
      target.icon_url = resolveIconUrl(target);
      if (target.icon_url) $("iconUrl").value = target.icon_url;
    }
    return target;
  }

  function beginHiUtilsTrace(attempt) {
    const original = window.HiUtils_createRequest;
    attempt.hiUtilsTrace = [];
    if (typeof original !== "function") return function () {};

    const wrapped = function (type, msg) {
      const entry = {timestamp:new Date().toISOString(), type:String(type), args:safeValue(msg)};
      try {
        const result = original(type, msg);
        entry.result = safeValue(result);
        attempt.hiUtilsTrace.push(entry);
        log("HiUtils " + String(type), entry);
        return result;
      } catch (e) {
        entry.error = String(e && e.message || e);
        attempt.hiUtilsTrace.push(entry);
        throw e;
      }
    };

    try {
      window.HiUtils_createRequest = wrapped;
      return function () {
        try { window.HiUtils_createRequest = original; } catch (_) {}
      };
    } catch (e) {
      attempt.hiUtilsTraceError = String(e && e.message || e);
      return function () {};
    }
  }

  async function saveTarget() {
    const r = await fetch("/api/config", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({nuvio: currentTarget()})
    });
    const data = await r.json();
    log("Target saved on Sidee host.", data);
    await getConfig();
  }

  function enumerateInterestingGlobals() {
    const names = new Set(KNOWN);
    let cursor = window;
    for (let depth = 0; cursor && depth < 4; depth++) {
      try { Object.getOwnPropertyNames(cursor).forEach((name) => names.add(name)); } catch (_) {}
      try { cursor = Object.getPrototypeOf(cursor); } catch (_) { break; }
    }
    return Array.from(names)
      .filter((name) => PERMISSION_PROBE_MATCHER.test(name))
      .sort()
      .slice(0, PROBE_LIMITS.maxGlobalMatches)
      .map(inspectGlobal);
  }

  function callGetter(name) {
    try {
      const fn = window[name];
      if (typeof fn !== "function") return {available:false};
      return {available:true, ok:true, value:safeValue(fn())};
    } catch (e) {
      return {available:true, ok:false, error:String(e && e.message || e)};
    }
  }

  async function scan() {
    logBox.textContent = "";
    log("Starting read-only scan.");
    const functions = enumerateInterestingGlobals();
    const device = {
      location: location.href,
      origin: location.origin,
      host: location.host,
      userAgent: navigator.userAgent,
      platform: navigator.platform,
      language: navigator.language,
      screen: {width:screen.width,height:screen.height,availWidth:screen.availWidth,availHeight:screen.availHeight}
    };
    SAFE_GETTERS.forEach((name) => { device[name] = callGetter(name); });

    state.scan = {
      timestamp:new Date().toISOString(),
      readOnly:true,
      device,
      globals:functions,
      capabilities:{
        installApp:typeof window.Hisense_installApp === "function",
        installAppV2:typeof window.Hisense_installApp_V2 === "function",
        uninstallApp:typeof window.Hisense_uninstallApp === "function",
        getInstalledApps:typeof window.Hisense_getInstalledApps === "function",
        hiUtils:typeof window.HiUtils_createRequest === "function",
        omi:Boolean(window.omi_platform && typeof window.omi_platform.sendPlatformMessage === "function"),
        operaOmi:Boolean(window.opera_omi && typeof window.opera_omi.sendPlatformMessage === "function")
      }
    };

    $("fnCount").textContent = String(functions.filter((x)=>x.available).length);
    $("firmware").textContent = device.Hisense_GetFirmWareVersion?.value || "unknown";
    $("model").textContent = device.Hisense_GetModelName?.value || "unknown";
    $("deviceBadge").textContent = state.scan.capabilities.installApp ? "VIDAA APIs detected" : "VIDAA detected / install API unavailable";
    log("Read-only scan complete.", state.scan);
    await saveReport("scan");
  }


  async function permissionProbe() {
    const stateEl = $("permissionProbeState");
    stateEl.textContent = "Running read-only permission probe…";

    const budget = createProbeBudget();
    const globals = enumerateInterestingGlobals();

    const supportAppConfig = probeSupportAppConfig(budget);

    const vowOSGlobal = inspectGlobal("vowOS");
    const vowOSValue = getGlobalDataValue("vowOS");
    let vowOSInspection = null;
    if (vowOSValue.data && vowOSValue.value !== null && ["object","function"].includes(typeof vowOSValue.value)) {
      vowOSInspection = inspectObjectTree(vowOSValue.value, "window.vowOS", budget);
    }

    const hiUtils = analyzeNamedFunction("HiUtils_createRequest");
    const inspectOnlyApis = INSPECT_ONLY_SECURITY_APIS.map(analyzeNamedFunction);

    const inspectedObjects = [];
    for (const globalRecord of globals) {
      if (budget.entries >= PROBE_LIMITS.maxEntries) break;
      if (globalRecord.name === "vowOS" || globalRecord.name === "Hisense_SupportAppConfig") continue;
      const dataValue = getGlobalDataValue(globalRecord.name);
      if (!dataValue.data || dataValue.value === null || typeof dataValue.value !== "object") continue;
      const inspection = inspectObjectTree(dataValue.value, globalRecord.path, budget);
      if (inspection.objects.length || inspection.entries.length || inspection.errors.length) {
        inspectedObjects.push(inspection);
      }
    }

    const summary = {
      status:"completed",
      interestingEntries:globals.length + budget.entries,
      globalMatches:globals.length,
      inspectedPropertyEntries:budget.entries,
      entryLimitReached:budget.limitReached,
      supportAppConfig:supportAppConfig.status,
      vowOS:vowOSGlobal.available ? "found" : "not found",
      hiUtils:hiUtils.present ? "found" : "not found"
    };

    state.permissionProbe = {
      timestamp:new Date().toISOString(),
      readOnly:true,
      limits:{...PROBE_LIMITS},
      environment:{
        href:location.href,
        origin:location.origin,
        host:location.host,
        userAgent:navigator.userAgent
      },
      summary,
      globals,
      supportAppConfig,
      hiUtils,
      vowOS:{
        present:vowOSGlobal.available,
        type:vowOSGlobal.type,
        descriptor:vowOSGlobal.descriptor || null,
        inspection:vowOSInspection
      },
      inspectOnlyApis,
      inspectedObjects,
      calls:{
        supportAppConfigCalled:supportAppConfig.called,
        otherVIDAAFunctionsCalled:[]
      },
      safety:{
        gettersInvoked:false,
        unknownMethodsInvoked:false,
        hiUtilsRequestsIssued:false,
        writesIssued:false
      }
    };

    stateEl.textContent =
      "Probe completed · " + summary.interestingEntries + " interesting entries · " +
      "Hisense_SupportAppConfig: " + summary.supportAppConfig + " · " +
      "vowOS: " + summary.vowOS + " · " +
      "HiUtils_createRequest: " + summary.hiUtils;

    log("Permission & AppConfig probe complete.", summary);
    await saveReport("permission-appconfig-probe");
  }

  function refreshLauncher(appId) {
    const payload = {
      type:"APPMessage", MsgType:"appControl", action:"updateAppState",
      source:"browser", startAppType:2,
      param:{event:"AllAppsUpdate",SubModuleName:"AllApps",startFrom:"",appInfo:appId || ""}
    };
    const text = JSON.stringify(payload);
    try {
      if (window.omi_platform && typeof window.omi_platform.sendPlatformMessage === "function") {
        return {attempted:true,bridge:"omi_platform",result:safeValue(window.omi_platform.sendPlatformMessage(text))};
      }
      if (window.opera_omi && typeof window.opera_omi.sendPlatformMessage === "function") {
        return {attempted:true,bridge:"opera_omi",result:safeValue(window.opera_omi.sendPlatformMessage(text))};
      }
      return {attempted:false,reason:"No OMI bridge"};
    } catch (e) {
      return {attempted:true,error:String(e && e.message || e)};
    }
  }

  async function callInstalledApps() {
    const fn = window.Hisense_getInstalledApps;
    if (typeof fn !== "function") return {available:false};
    return await new Promise((resolve) => {
      let done = false;
      const finish = (value) => { if (!done) { done = true; resolve(value); } };
      const timer = setTimeout(() => finish({available:true,ok:true,returnValue:null,callbackTimedOut:true}), 1200);
      try {
        let ret;
        ret = fn(function () {
          clearTimeout(timer);
          finish({available:true,ok:true,returnValue:safeValue(ret),callback:Array.from(arguments).map(safeValue)});
        });
        if (ret !== undefined) {
          clearTimeout(timer);
          finish({available:true,ok:true,returnValue:safeValue(ret)});
        }
      } catch (e) {
        clearTimeout(timer);
        finish({available:true,ok:false,error:String(e && e.message || e)});
      }
    });
  }

  function readAppInfo() {
    const fn = window.HiUtils_createRequest;
    if (typeof fn !== "function") return {available:false};
    try {
      const result = fn("fileRead", {path:"websdk/Appinfo.json",mode:6});
      return {available:true,ok:Boolean(result && result.ret),result:safeValue(result)};
    } catch (e) {
      return {available:true,ok:false,error:String(e && e.message || e)};
    }
  }

  function containsTarget(value, target) {
    const haystack = safeJson(value).toLowerCase();
    return haystack.includes(target.app_id.toLowerCase()) ||
      haystack.includes(target.app_name.toLowerCase()) ||
      (target.app_url && haystack.includes(target.app_url.toLowerCase()));
  }

  async function verify(deep) {
    const target = currentTarget();
    const installedApps = await callInstalledApps();
    const appInfo = deep ? readAppInfo() : {available:typeof window.HiUtils_createRequest === "function",skipped:true};
    const verifiedByInstalledApps = installedApps.ok && containsTarget(installedApps, target);
    const verifiedByAppInfo = appInfo.ok && containsTarget(appInfo, target);
    const result = {
      timestamp:new Date().toISOString(),
      target,
      installedApps,
      appInfo,
      verified:Boolean(verifiedByInstalledApps || verifiedByAppInfo),
      evidence: verifiedByInstalledApps ? "Hisense_getInstalledApps" : verifiedByAppInfo ? "websdk/Appinfo.json" : null
    };
    state.verification = result;
    $("verifyOutput").textContent = safeJson(result);
    log("Verification complete.", result);
    return result;
  }

  function buildV2AppInfo(target, icon) {
    return {
      Id: target.app_id,
      appId: target.app_id,
      AppName: target.app_name,
      name: target.app_name,
      Title: target.app_name,
      URL: target.app_url,
      url: target.app_url,
      StartCommand: target.app_url,
      Thumb: icon,
      Icon_96: icon,
      Image: icon,
      IconURL: icon,
      icon: icon,
      StoreType: target.store_type || "store",
      storeType: target.store_type || "store",
      PreInstall: false,
      isShowOnLauncher: true
    };
  }

  async function installWithMethod(method) {
    const target = currentTarget();
    if (!target.app_id || !target.app_name || !target.app_url) {
      setInstallState("App ID, name and URL are required.", "bad");
      return;
    }

    const isV2 = method === "v2";
    const api = isV2 ? window.Hisense_installApp_V2 : window.Hisense_installApp;
    if (typeof api !== "function") {
      setInstallState((isV2 ? "Hisense_installApp_V2" : "Hisense_installApp") + " is not available in this browser context.", "bad");
      return;
    }

    const icon = resolveIconUrl(target);
    if (!icon) {
      setInstallState("A valid icon URL is required.", "bad");
      return;
    }
    if ($("iconUrl").value.trim() !== icon) $("iconUrl").value = icon;

    const attempt = {
      timestamp:new Date().toISOString(),
      method,
      target:{...target, resolved_icon_url:icon},
      beforeAppInfo:readAppInfo(),
      callback:null,
      returnValue:null,
      refresh:null,
      verification:null,
      hiUtilsTrace:[]
    };
    state.installAttempts.push(attempt);

    setInstallState("Calling " + (isV2 ? "Hisense_installApp_V2" : "Hisense_installApp") + "…", "warn");
    const restoreTrace = beginHiUtilsTrace(attempt);
    let callbackFinished = false;

    const callback = async function (code) {
      if (callbackFinished) return;
      callbackFinished = true;
      restoreTrace();
      attempt.callback = {code:safeValue(code),receivedAt:new Date().toISOString()};
      log((isV2 ? "Hisense_installApp_V2" : "Hisense_installApp") + " callback.", attempt.callback);

      attempt.afterCallbackAppInfo = readAppInfo();
      attempt.refresh = refreshLauncher(target.app_id);
      await new Promise((r)=>setTimeout(r,1500));
      attempt.afterRefreshAppInfo = readAppInfo();
      attempt.verification = await verify(true);

      if (attempt.verification.verified) {
        setInstallState("Verified: Nuvio is present (" + attempt.verification.evidence + "). Restart the TV if the launcher has not refreshed yet.", "good");
      } else if (Number(code) === 0) {
        const installTrace = (attempt.hiUtilsTrace || []).filter((x)=>x.type === "installApplication");
        const suffix = installTrace.length ? " Internal installApplication trace captured in the report." : " No installApplication trace was intercepted.";
        setInstallState("VIDAA returned code 0, but Sidee could NOT verify the app. Request accepted ≠ installed." + suffix, "warn");
      } else {
        setInstallState("VIDAA install callback returned: " + String(code) + ".", "bad");
      }
      await saveReport("install-" + method);
    };

    try {
      if (isV2) {
        const appInfo = buildV2AppInfo(target, icon);
        attempt.v2Payload = appInfo;
        attempt.returnValue = safeValue(api(appInfo, callback));
      } else {
        attempt.returnValue = safeValue(api(
          target.app_id, target.app_name,
          icon, icon, icon,
          target.app_url, target.store_type || "store",
          callback
        ));
      }

      setTimeout(function () {
        if (!callbackFinished) {
          restoreTrace();
          attempt.callbackTimeout = true;
          setInstallState("The install API did not call back within 5 seconds. Save the report.", "warn");
        }
      }, 5000);
    } catch (e) {
      restoreTrace();
      attempt.error = String(e && e.message || e);
      setInstallState("Install call threw: " + attempt.error, "bad");
      log("Install exception.", attempt);
      await saveReport("install-" + method + "-error");
    }
  }

  async function install() {
    return installWithMethod("legacy");
  }

  async function installV2() {
    return installWithMethod("v2");
  }

  async function uninstall() {
    const target = currentTarget();
    if (typeof window.Hisense_uninstallApp !== "function") {
      setInstallState("Hisense_uninstallApp is unavailable.", "bad");
      return;
    }
    try {
      window.Hisense_uninstallApp(target.app_id, async function (status) {
        log("Uninstall callback.", {status:safeValue(status)});
        refreshLauncher("");
        await new Promise((r)=>setTimeout(r,1200));
        const result = await verify(true);
        setInstallState(result.verified ? "Uninstall callback returned, but the app is still visible to verification." : "App is no longer visible to Sidee verification.", result.verified ? "warn" : "good");
        await saveReport("uninstall");
      });
    } catch (e) {
      setInstallState("Uninstall call threw: " + String(e && e.message || e), "bad");
    }
  }

  async function saveReport(reason) {
    const payload = {
      reason,
      generatedAt:new Date().toISOString(),
      state,
      currentTarget:currentTarget()
    };
    try {
      const r = await fetch("/api/report", {
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify(payload)
      });
      const data = await r.json();
      log("Report saved on PC: " + (data.file || "unknown"));
    } catch (e) {
      log("Could not save report.", String(e));
    }
  }

  $("scanBtn").addEventListener("click", scan);
  $("permissionProbeBtn").addEventListener("click", permissionProbe);
  $("saveBtn").addEventListener("click", saveTarget);
  $("verifyBtn").addEventListener("click", () => verify(false));
  $("deepBtn").addEventListener("click", () => verify(true));
  $("installBtn").addEventListener("click", install);
  $("installV2Btn").addEventListener("click", installV2);
  $("uninstallBtn").addEventListener("click", uninstall);
  $("reportBtn").addEventListener("click", () => saveReport("manual"));

  window.addEventListener("keydown", (e) => {
    if (["ArrowUp","ArrowDown","ArrowLeft","ArrowRight"].includes(e.key)) {
      const list = Array.from(document.querySelectorAll("button,input")).filter((x)=>!x.disabled);
      const i = Math.max(0, list.indexOf(document.activeElement));
      const delta = (e.key === "ArrowUp" || e.key === "ArrowLeft") ? -1 : 1;
      list[(i + delta + list.length) % list.length]?.focus();
      e.preventDefault();
    }
  });

  getConfig().then(() => {
    log("Sidee UI ready.");
    $("deviceBadge").textContent = typeof window.Hisense_GetFirmWareVersion === "function" ? "VIDAA browser detected" : "Waiting for VIDAA APIs";
  }).catch((e)=>log("Config load failed.",String(e)));
})();
