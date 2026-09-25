(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const logBox = $("console");
  const SESSION_ID_RE = /^sidee-\d{8}-\d{6}-[a-f0-9]{4}$/;

  function pad2(value) {
    return String(value).padStart(2, "0");
  }

  function createSessionId() {
    const now = new Date();
    const stamp =
      String(now.getFullYear()) +
      pad2(now.getMonth() + 1) +
      pad2(now.getDate()) + "-" +
      pad2(now.getHours()) +
      pad2(now.getMinutes()) +
      pad2(now.getSeconds());
    let suffix = "";
    try {
      const bytes = new Uint8Array(2);
      crypto.getRandomValues(bytes);
      suffix = Array.from(bytes).map((value) => value.toString(16).padStart(2, "0")).join("");
    } catch (_) {
      suffix = Math.floor(Math.random() * 65536).toString(16).padStart(4, "0");
    }
    return "sidee-" + stamp + "-" + suffix;
  }

  function getSessionId() {
    const storageKey = "sidee.sessionId";
    try {
      const existing = sessionStorage.getItem(storageKey);
      if (existing && SESSION_ID_RE.test(existing)) return existing;
      const created = createSessionId();
      sessionStorage.setItem(storageKey, created);
      return created;
    } catch (_) {
      return createSessionId();
    }
  }

  function createSessionReport() {
    const now = new Date().toISOString();
    return {
      sessionId:getSessionId(),
      startedAt:now,
      updatedAt:now,
      summary:{
        origin:location.origin,
        installApi:"UNKNOWN",
        appConfigProbe:"UNKNOWN",
        installRequest:"UNKNOWN",
        internalReason:"UNKNOWN",
        permissionCode:"UNKNOWN",
        verification:"UNKNOWN",
        conclusion:"UNKNOWN"
      },
      environment:{},
      permissionProbe:{},
      clientIdentityProbe:{},
      target:{},
      installDiagnostic:{status:"UNKNOWN",attempts:[]},
      verification:{},
      hiUtilsTrace:[],
      raw:{snapshots:{}}
    };
  }

  const state = {
    config:null,
    report:createSessionReport()
  };
  let reportSaveChain = Promise.resolve();
  let diagnosticRunning = false;
  let clientContextCaptureActive = false;

  const STATUS = Object.freeze({
    AVAILABLE:"AVAILABLE",
    REQUESTED:"REQUESTED",
    REJECTED:"REJECTED",
    VERIFIED_INSTALLED:"VERIFIED INSTALLED",
    NOT_INSTALLED:"NOT INSTALLED",
    UNKNOWN:"UNKNOWN"
  });

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
    "Hisense_RSADecrypt","HiUtils_createRequest","vowOS","vowOSContext","clientInformation","omi_platform","opera_omi"
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

  const SERIALIZE_LIMITS = Object.freeze({
    maxDepth: PROBE_LIMITS.maxDepth + 3,
    maxPropertiesPerObject: PROBE_LIMITS.maxPropertiesPerObject,
    maxEntries: PROBE_LIMITS.maxEntries,
    maxArrayItems: 250,
    maxStringLength: PROBE_LIMITS.maxFunctionSourceLength
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

  function getDataPropertyValue(root, name, maxDepth) {
    if (root === null || !["object","function"].includes(typeof root)) {
      return {found:false,data:false,error:"Root is unavailable"};
    }
    const found = findPropertyDescriptor(root, name, maxDepth === undefined ? 4 : maxDepth);
    if (!found) return {found:false,data:false,error:null};
    if (found.error) return {found:true,data:false,error:found.error,ownerDepth:found.ownerDepth};
    const descriptor = found.descriptor;
    if (!Object.prototype.hasOwnProperty.call(descriptor, "value")) {
      return {found:true,data:false,accessor:true,descriptor,ownerDepth:found.ownerDepth};
    }
    return {found:true,data:true,value:descriptor.value,descriptor,ownerDepth:found.ownerDepth};
  }

  function readOnlyCallRecord(root, name, label) {
    const property = getDataPropertyValue(root, name, 4);
    const record = {
      status:"unavailable",
      called:false,
      type:null,
      value:null,
      error:null,
      label:label || name
    };
    if (!property.found) return record;
    if (property.error) {
      record.status = "error";
      record.error = property.error;
      return record;
    }
    if (!property.data) {
      record.error = property.accessor ? "Accessor not invoked" : "Data property unavailable";
      return record;
    }
    if (typeof property.value !== "function") {
      record.type = property.value === null ? "null" : typeof property.value;
      record.error = "Not a function";
      return record;
    }

    record.called = true;
    try {
      const value = property.value.call(root);
      record.status = "returned";
      record.type = value === null ? "null" : typeof value;
      record.value = isPrimitiveValue(value) ? snapshotPrimitive(value) : safeValue(value);
    } catch (error) {
      record.status = "error";
      record.error = errorText(error);
    }
    return record;
  }

  function readOnlyGlobalCallRecord(name) {
    const property = getGlobalDataValue(name);
    const record = {
      status:"unavailable",
      called:false,
      type:null,
      value:null,
      error:null,
      label:name
    };
    if (!property.found) return record;
    if (property.error) {
      record.status = "error";
      record.error = property.error;
      return record;
    }
    if (!property.data) {
      record.error = property.accessor ? "Accessor not invoked" : "Data property unavailable";
      return record;
    }
    if (typeof property.value !== "function") {
      record.type = property.value === null ? "null" : typeof property.value;
      record.error = "Not a function";
      return record;
    }

    record.called = true;
    try {
      const value = property.value();
      record.status = "returned";
      record.type = value === null ? "null" : typeof value;
      record.value = isPrimitiveValue(value) ? snapshotPrimitive(value) : safeValue(value);
    } catch (error) {
      record.status = "error";
      record.error = errorText(error);
    }
    return record;
  }

  function inspectClientInformation() {
    const record = inspectGlobal("clientInformation");
    return {
      called:false,
      status:record.available ? (record.type === "accessor" ? "accessor-inspect-only" : "inspect-only") : "unavailable",
      type:record.type,
      descriptor:record.descriptor || null,
      getterSource:record.descriptor && record.descriptor.getterSource || null,
      error:record.error || null
    };
  }

  function unavailableIdentityRecord(message) {
    return {
      status:"unavailable",
      called:false,
      type:null,
      value:null,
      error:message || null
    };
  }

  function captureClientIdentityContext(includeClientInformation) {
    const timestamp = new Date().toISOString();
    if (clientContextCaptureActive) {
      return {
        timestamp,
        serviceIdentifier:unavailableIdentityRecord("Identity capture already in progress"),
        appIdentifier:unavailableIdentityRecord("Identity capture already in progress"),
        appId:unavailableIdentityRecord("Identity capture already in progress"),
        roleId:unavailableIdentityRecord("Identity capture already in progress"),
        customerId:unavailableIdentityRecord("Identity capture already in progress")
      };
    }

    clientContextCaptureActive = true;
    try {
      let serviceIdentifier = unavailableIdentityRecord("vowOS.service.getIdentifier unavailable");
      const vowOSValue = getGlobalDataValue("vowOS");
      if (vowOSValue.data && vowOSValue.value !== null && ["object","function"].includes(typeof vowOSValue.value)) {
        const serviceProperty = getDataPropertyValue(vowOSValue.value, "service", 4);
        if (serviceProperty.error) {
          serviceIdentifier = {
            status:"error",called:false,type:null,value:null,error:serviceProperty.error
          };
        } else if (serviceProperty.data && serviceProperty.value !== null && ["object","function"].includes(typeof serviceProperty.value)) {
          serviceIdentifier = readOnlyCallRecord(serviceProperty.value, "getIdentifier", "vowOS.service.getIdentifier");
        } else if (serviceProperty.accessor) {
          serviceIdentifier = unavailableIdentityRecord("vowOS.service accessor not invoked");
        }
      } else if (vowOSValue.accessor) {
        serviceIdentifier = unavailableIdentityRecord("vowOS accessor not invoked");
      } else if (vowOSValue.error) {
        serviceIdentifier = {
          status:"error",called:false,type:null,value:null,error:vowOSValue.error
        };
      }

      let appIdentifier = unavailableIdentityRecord("vowOSContext.getAppIdentifier unavailable");
      let appId = unavailableIdentityRecord("vowOSContext.getAppId unavailable");
      const contextValue = getGlobalDataValue("vowOSContext");
      if (contextValue.data && contextValue.value !== null && ["object","function"].includes(typeof contextValue.value)) {
        appIdentifier = readOnlyCallRecord(contextValue.value, "getAppIdentifier", "vowOSContext.getAppIdentifier");
        appId = readOnlyCallRecord(contextValue.value, "getAppId", "vowOSContext.getAppId");
      } else if (contextValue.accessor) {
        appIdentifier = unavailableIdentityRecord("vowOSContext accessor not invoked");
        appId = unavailableIdentityRecord("vowOSContext accessor not invoked");
      } else if (contextValue.error) {
        appIdentifier = {status:"error",called:false,type:null,value:null,error:contextValue.error};
        appId = {status:"error",called:false,type:null,value:null,error:contextValue.error};
      }

      const result = {
        timestamp,
        serviceIdentifier,
        appIdentifier,
        appId,
        roleId:readOnlyGlobalCallRecord("Hisense_GetRoleID"),
        customerId:readOnlyGlobalCallRecord("Hisense_GetCustomerID")
      };
      if (includeClientInformation) result.clientInformation = inspectClientInformation();
      return result;
    } finally {
      clientContextCaptureActive = false;
    }
  }

  function traceIdentityValue(record) {
    if (record && record.status === "returned") return safeValue(record.value);
    if (record && record.status === "error") return "ERROR";
    return "UNAVAILABLE";
  }

  function captureTraceClientContext() {
    const identity = captureClientIdentityContext(false);
    return {
      serviceIdentifier:traceIdentityValue(identity.serviceIdentifier),
      appIdentifier:traceIdentityValue(identity.appIdentifier),
      appId:traceIdentityValue(identity.appId),
      roleId:traceIdentityValue(identity.roleId),
      customerId:traceIdentityValue(identity.customerId)
    };
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

  function safeSerialize(value) {
    const budget = {entries:0};
    const seen = typeof WeakSet === "function" ? new WeakSet() : [];

    const markSeen = (candidate) => {
      if (candidate === null || !["object","function"].includes(typeof candidate)) return false;
      if (seen instanceof WeakSet) {
        if (seen.has(candidate)) return true;
        seen.add(candidate);
        return false;
      }
      if (seen.indexOf(candidate) >= 0) return true;
      seen.push(candidate);
      return false;
    };

    const walk = (candidate, depth) => {
      if (candidate === undefined) return "[undefined]";
      if (candidate === null || ["string","number","boolean"].includes(typeof candidate)) {
        return typeof candidate === "string"
          ? truncateText(candidate, SERIALIZE_LIMITS.maxStringLength)
          : candidate;
      }
      if (typeof candidate === "bigint" || typeof candidate === "symbol") {
        return truncateText(String(candidate), SERIALIZE_LIMITS.maxStringLength);
      }
      if (typeof candidate === "function") {
        return "[Function" + (candidate.name ? ": " + truncateText(candidate.name, 120) : "") + "]";
      }
      if (candidate instanceof Error) {
        return {
          name:truncateText(candidate.name || "Error", 120),
          message:truncateText(candidate.message || "", SERIALIZE_LIMITS.maxStringLength),
          stack:candidate.stack ? truncateText(candidate.stack, SERIALIZE_LIMITS.maxStringLength) : null
        };
      }
      if (candidate instanceof Date) return candidate.toISOString();
      if (typeof Node !== "undefined" && candidate instanceof Node) {
        return "[DOM " + truncateText(candidate.nodeName || "Node", 120) + "]";
      }
      if (depth >= SERIALIZE_LIMITS.maxDepth) {
        let name = "Object";
        try { name = candidate.constructor && candidate.constructor.name || name; } catch (_) {}
        return "[MaxDepth: " + truncateText(name, 120) + "]";
      }
      if (markSeen(candidate)) return "[Circular]";
      if (budget.entries >= SERIALIZE_LIMITS.maxEntries) return "[EntryLimit]";

      if (Array.isArray(candidate)) {
        const result = [];
        const length = Math.min(candidate.length, SERIALIZE_LIMITS.maxArrayItems);
        for (let i = 0; i < length; i++) {
          if (budget.entries >= SERIALIZE_LIMITS.maxEntries) {
            result.push("[EntryLimit]");
            break;
          }
          budget.entries += 1;
          let descriptor = null;
          try { descriptor = Object.getOwnPropertyDescriptor(candidate, String(i)); } catch (_) {}
          if (!descriptor) {
            result.push("[missing]");
          } else if (Object.prototype.hasOwnProperty.call(descriptor, "value")) {
            result.push(walk(descriptor.value, depth + 1));
          } else {
            result.push("[Accessor]");
          }
        }
        if (candidate.length > length) result.push("[+" + (candidate.length - length) + " items truncated]");
        return result;
      }

      const result = {};
      let names = [];
      try { names = Object.getOwnPropertyNames(candidate); } catch (error) {
        return "[Uninspectable: " + errorText(error) + "]";
      }
      const selected = names.slice(0, SERIALIZE_LIMITS.maxPropertiesPerObject);
      for (const name of selected) {
        if (budget.entries >= SERIALIZE_LIMITS.maxEntries) {
          result.__truncated = "[EntryLimit]";
          break;
        }
        budget.entries += 1;
        let descriptor = null;
        try { descriptor = Object.getOwnPropertyDescriptor(candidate, name); } catch (error) {
          result[name] = "[Descriptor error: " + errorText(error) + "]";
          continue;
        }
        if (!descriptor) continue;
        if (!Object.prototype.hasOwnProperty.call(descriptor, "value")) {
          result[name] = "[Accessor]";
          continue;
        }
        result[name] = walk(descriptor.value, depth + 1);
      }
      if (names.length > selected.length) result.__truncatedProperties = names.length - selected.length;
      return result;
    };

    try {
      return walk(value, 0);
    } catch (error) {
      return {serializationError:errorText(error)};
    }
  }

  function safeJson(value) {
    try { return JSON.stringify(safeSerialize(value), null, 2); } catch (error) {
      return JSON.stringify({serializationError:errorText(error)});
    }
  }

  function safeValue(value) {
    return safeSerialize(value);
  }

  function syncTargetToReport() {
    state.report.target = safeValue(currentTarget());
    return state.report.target;
  }

  function captureRawSnapshot(name, value, replaceExisting) {
    const snapshots = state.report.raw.snapshots;
    if (replaceExisting || !Object.prototype.hasOwnProperty.call(snapshots, name)) {
      snapshots[name] = safeValue(value);
    }
  }

  function getterValue(device, name) {
    const entry = device && device[name];
    return entry && entry.ok ? entry.value : null;
  }

  function compactSupportAppConfigResult(result) {
    if (!result) return null;
    const compact = {status:result.status || null};
    if (result.resultType) compact.type = result.resultType;
    if (Object.prototype.hasOwnProperty.call(result, "resultValue")) compact.value = safeValue(result.resultValue);
    if (result.error) compact.error = truncateText(result.error, PROBE_LIMITS.maxStringLength);
    return compact;
  }

  function currentReportFileName() {
    return "sidee-session-" + state.report.sessionId.slice("sidee-".length) + ".json";
  }

  function summaryStatusClass(value) {
    if ([STATUS.AVAILABLE, STATUS.VERIFIED_INSTALLED, "COMPLETED"].includes(value)) return "good";
    if ([STATUS.REJECTED, STATUS.NOT_INSTALLED].includes(value)) return "bad";
    if (value === STATUS.REQUESTED) return "warn";
    return "";
  }

  function setSummaryValue(id, value) {
    const el = $(id);
    if (!el) return;
    const text = value === null || value === undefined || value === "" ? STATUS.UNKNOWN : String(value);
    el.textContent = text;
    el.className = "summaryValue " + summaryStatusClass(text);
  }

  function environmentSummaryText() {
    const summary = state.report.summary;
    const os = summary.OS || "VIDAA";
    return summary.apiVersion ? os + " / API " + summary.apiVersion : os;
  }

  function renderSummary() {
    setSummaryValue("summaryEnvironment", environmentSummaryText());
    setSummaryValue("summaryOrigin", state.report.summary.origin || location.origin);
    setSummaryValue("summaryInstallApi", state.report.summary.installApi || STATUS.UNKNOWN);
    setSummaryValue("summaryAppConfig", state.report.summary.appConfigProbe || STATUS.UNKNOWN);
    setSummaryValue("summaryInstallRequest", state.report.summary.installRequest || STATUS.UNKNOWN);
    setSummaryValue("summaryInternalReason", state.report.summary.internalReason || STATUS.UNKNOWN);
    setSummaryValue("summaryPermissionCode", state.report.summary.permissionCode ?? STATUS.UNKNOWN);
    setSummaryValue("summaryVerification", state.report.summary.verification || STATUS.UNKNOWN);
    const reportName = $("reportFileName");
    if (reportName) reportName.textContent = currentReportFileName();
  }

  function updateSummaryFromEnvironment(environment) {
    const device = environment.device || {};
    const capabilities = environment.capabilities || {};
    const installAvailable = Boolean(capabilities.installApp || capabilities.installAppV2);
    Object.assign(state.report.summary, {
      firmware:getterValue(device, "Hisense_GetFirmWareVersion"),
      model:getterValue(device, "Hisense_GetModelName"),
      OS:getterValue(device, "Hisense_GetOSVersion"),
      apiVersion:getterValue(device, "Hisense_GetApiVersion"),
      browser:getterValue(device, "Hisense_GetCurrentBrowser") || device.userAgent || null,
      origin:device.origin || location.origin,
      legacyAvailable:Boolean(capabilities.installApp),
      v2Available:Boolean(capabilities.installAppV2),
      getInstalledAppsAvailable:Boolean(capabilities.getInstalledApps),
      supportAppConfigAvailable:Boolean(environment.supportAppConfigAvailable),
      installApi:installAvailable ? STATUS.AVAILABLE : STATUS.UNKNOWN
    });
    renderSummary();
  }

  function findFirstValueByKeys(value, keys) {
    const wanted = new Set(keys.map((key) => key.toLowerCase()));
    const queue = [value];
    const seen = new Set();
    let visited = 0;
    while (queue.length && visited < 300) {
      const current = queue.shift();
      visited += 1;
      if (current === null || typeof current !== "object") continue;
      if (seen.has(current)) continue;
      seen.add(current);
      for (const key of Object.keys(current)) {
        if (wanted.has(key.toLowerCase())) return current[key];
      }
      for (const child of Object.values(current)) {
        if (child !== null && typeof child === "object") queue.push(child);
      }
    }
    return null;
  }

  function installTraceDetails(attempt) {
    const installTrace = (attempt.hiUtilsTrace || []).filter((entry) => String(entry.type).toLowerCase() === "installapplication");
    const latestTrace = installTrace.length ? installTrace[installTrace.length - 1] : null;
    const traceResult = latestTrace ? (latestTrace.result || latestTrace.error || latestTrace) : null;
    const internalRet = findFirstValueByKeys(traceResult, ["ret"]);
    const errorCode = findFirstValueByKeys(traceResult, ["code","errorCode"]);
    const errorMessage = findFirstValueByKeys(traceResult, ["message","msg","error"]);
    return {
      internalRet,
      errorCode,
      errorMessage:errorMessage === null || errorMessage === undefined ? null : String(errorMessage),
      appConfigPermissionFailure:
        Number(errorCode) === 503 &&
        /permission check error|appconfig/i.test(String(errorMessage || ""))
    };
  }

  function classifyInstallAttempt(attempt, verification) {
    const details = installTraceDetails(attempt);
    if (verification && verification.verified) return STATUS.VERIFIED_INSTALLED;
    if (details.appConfigPermissionFailure) return STATUS.REJECTED;
    if (details.internalRet === false || attempt.returnValue === false) return STATUS.REJECTED;
    if (attempt.callback && Number(attempt.callback.code) !== 0) return STATUS.REJECTED;
    if (attempt.error || attempt.callbackTimeout || attempt.unavailable) return STATUS.UNKNOWN;
    if (attempt.requested) return STATUS.REQUESTED;
    return STATUS.UNKNOWN;
  }

  function updateInstallSummary(attempt, verification) {
    const details = installTraceDetails(attempt);
    const classification = classifyInstallAttempt(attempt, verification);
    attempt.classification = classification;
    attempt.internal = safeValue(details);

    state.report.summary.installRequest = classification;
    if (details.errorCode !== null && details.errorCode !== undefined) {
      state.report.summary.permissionCode = details.errorCode;
    }
    if (details.appConfigPermissionFailure) {
      state.report.summary.internalReason = "APP CONFIG PERMISSION CHECK FAILED";
      state.report.summary.permissionCode = 503;
    } else if (details.errorMessage) {
      state.report.summary.internalReason = truncateText(details.errorMessage, 180);
    } else if (attempt.error) {
      state.report.summary.internalReason = truncateText(attempt.error, 180);
    }

    if (verification) {
      state.report.summary.verification = verification.verified ? STATUS.VERIFIED_INSTALLED : STATUS.NOT_INSTALLED;
    }
    state.report.summary.conclusion =
      verification && verification.verified ? STATUS.VERIFIED_INSTALLED : classification;
    renderSummary();
    return classification;
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

  function compactHiUtilsTraceResult(result) {
    if (result === undefined) return null;
    const compact = {
      type:result === null ? "null" : typeof result
    };
    const ret = findFirstValueByKeys(result, ["ret"]);
    const code = findFirstValueByKeys(result, ["code","errorCode"]);
    const message = findFirstValueByKeys(result, ["message","msg","error"]);
    if (ret !== null && ret !== undefined) compact.ret = safeValue(ret);
    if (code !== null && code !== undefined) compact.code = safeValue(code);
    if (message !== null && message !== undefined) compact.message = truncateText(String(message), 300);
    return compact;
  }

  function recordSessionHiUtilsTrace(entry, source) {
    if (!Array.isArray(state.report.hiUtilsTrace)) state.report.hiUtilsTrace = [];
    const record = {
      timestamp:entry.timestamp || new Date().toISOString(),
      source:source || "unknown",
      type:String(entry.type || ""),
      args:safeValue(entry.args),
      clientContext:safeValue(entry.clientContext || captureTraceClientContext())
    };
    if (Object.prototype.hasOwnProperty.call(entry, "result")) {
      record.result = compactHiUtilsTraceResult(entry.result);
    }
    if (entry.error) record.error = truncateText(String(entry.error), PROBE_LIMITS.maxStringLength);
    state.report.hiUtilsTrace.push(record);
    if (state.report.hiUtilsTrace.length > 120) {
      state.report.hiUtilsTrace.splice(0, state.report.hiUtilsTrace.length - 120);
    }
  }

  function beginHiUtilsTrace(attempt) {
    const original = window.HiUtils_createRequest;
    attempt.hiUtilsTrace = [];
    if (typeof original !== "function") return function () {};

    const wrapped = function (type, msg) {
      if (clientContextCaptureActive) return original(type, msg);
      const entry = {
        timestamp:new Date().toISOString(),
        type:String(type),
        args:safeValue(msg),
        clientContext:captureTraceClientContext()
      };
      try {
        const result = original(type, msg);
        entry.result = safeValue(result);
        attempt.hiUtilsTrace.push(entry);
        recordSessionHiUtilsTrace(entry, "install-" + attempt.method);
        log("HiUtils trace captured: " + String(type) + ".", {
          type:entry.type,
          ret:findFirstValueByKeys(entry.result, ["ret"]),
          code:findFirstValueByKeys(entry.result, ["code","errorCode"]),
          message:findFirstValueByKeys(entry.result, ["message","msg","error"])
        });
        return result;
      } catch (e) {
        entry.error = errorText(e);
        attempt.hiUtilsTrace.push(entry);
        recordSessionHiUtilsTrace(entry, "install-" + attempt.method);
        log("HiUtils trace error: " + String(type) + ".", {error:entry.error});
        throw e;
      }
    };

    try {
      window.HiUtils_createRequest = wrapped;
      return function () {
        try { window.HiUtils_createRequest = original; } catch (_) {}
      };
    } catch (e) {
      attempt.hiUtilsTraceError = errorText(e);
      return function () {};
    }
  }

  async function saveTarget() {
    const r = await fetch("/api/config", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({nuvio: currentTarget()})
    });
    const data = await r.json();
    log("Target saved on Sidee host.", {ok:Boolean(data && data.ok)});
    await getConfig();
    syncTargetToReport();
    await saveReport("target");
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
    log("Device scan — running");
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

    const supportAppConfigGlobal = inspectGlobal("Hisense_SupportAppConfig");
    const environment = {
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
      },
      supportAppConfigAvailable:Boolean(supportAppConfigGlobal.available && supportAppConfigGlobal.type === "function")
    };
    state.report.environment = environment;
    updateSummaryFromEnvironment(state.report.environment);
    syncTargetToReport();

    $("fnCount").textContent = String(functions.filter((x)=>x.available).length);
    $("firmware").textContent = state.report.summary.firmware || "unknown";
    $("model").textContent = state.report.summary.model || "unknown";
    $("deviceBadge").textContent = environment.capabilities.installApp ? "VIDAA APIs detected" : "VIDAA detected / install API unavailable";
    const availableCount = functions.filter((x) => x.available).length;
    log("Device scan complete — " + availableCount + " VIDAA APIs");
    renderSummary();
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

    state.report.permissionProbe = {
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
    state.report.summary.supportAppConfigAvailable = Boolean(supportAppConfig.present);
    state.report.summary.supportAppConfigResult = compactSupportAppConfigResult(supportAppConfig);
    state.report.summary.appConfigProbe = "COMPLETED";
    renderSummary();

    stateEl.textContent =
      "Probe completed · " + summary.interestingEntries + " interesting entries · " +
      "Hisense_SupportAppConfig: " + summary.supportAppConfig + " · " +
      "vowOS: " + summary.vowOS + " · " +
      "HiUtils_createRequest: " + summary.hiUtils;

    log("Permission probe — " + summary.interestingEntries + " relevant runtime entries");
    log("Hisense_SupportAppConfig — " + summary.supportAppConfig);
    await saveReport("permission-appconfig-probe");
  }

  function identityDisplayValue(record) {
    if (!record || record.status === "unavailable") return "UNAVAILABLE";
    if (record.status === "error") return "ERROR";
    if (record.status !== "returned") return String(record.status || "UNAVAILABLE").toUpperCase();
    if (record.value === null) return "null";
    if (typeof record.value === "object") return truncateText(safeJson(record.value), 180);
    return String(record.value);
  }

  function renderClientIdentityProbe(result) {
    setSummaryValue("serviceIdentifierValue", identityDisplayValue(result.serviceIdentifier));
    setSummaryValue("appIdentifierValue", identityDisplayValue(result.appIdentifier));
    setSummaryValue("appIdValue", identityDisplayValue(result.appId));
    setSummaryValue("roleIdValue", identityDisplayValue(result.roleId));
    setSummaryValue("customerIdValue", identityDisplayValue(result.customerId));
  }

  async function clientIdentityProbe() {
    const stateEl = $("clientIdentityProbeState");
    if (stateEl) stateEl.textContent = "Running read-only client identity probe…";

    const result = captureClientIdentityContext(true);
    result.readOnly = true;
    result.comparison = {
      serviceAndAppIdentifierComparable:
        result.serviceIdentifier.status === "returned" &&
        result.appIdentifier.status === "returned",
      serviceAndAppIdentifierEqual:
        result.serviceIdentifier.status === "returned" &&
        result.appIdentifier.status === "returned"
          ? Object.is(result.serviceIdentifier.value, result.appIdentifier.value)
          : null
    };
    result.safety = {
      clientInformationCalled:false,
      stateChangingCallsIssued:false,
      settersCalled:false,
      signingCallsIssued:false,
      writesIssued:false
    };

    state.report.clientIdentityProbe = safeValue(result);
    renderClientIdentityProbe(result);
    if (stateEl) {
      stateEl.textContent =
        "Probe completed · identifier " + identityDisplayValue(result.serviceIdentifier) +
        " · appIdentifier " + identityDisplayValue(result.appIdentifier) +
        " · appId " + identityDisplayValue(result.appId);
    }
    log("Client identity probe — read-only context captured");
    await saveReport("client-identity-probe");
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
          finish({available:true,ok:true,returnValue:ret,callback:Array.from(arguments)});
        });
        if (ret !== undefined) {
          clearTimeout(timer);
          finish({available:true,ok:true,returnValue:ret});
        }
      } catch (e) {
        clearTimeout(timer);
        finish({available:true,ok:false,error:errorText(e)});
      }
    });
  }

  function readAppInfo() {
    const fn = window.HiUtils_createRequest;
    if (typeof fn !== "function") return {available:false};
    const args = {path:"websdk/Appinfo.json",mode:6};
    const traceEntry = {
      timestamp:new Date().toISOString(),
      type:"fileRead",
      args:safeValue(args),
      clientContext:captureTraceClientContext()
    };
    try {
      const result = fn("fileRead", args);
      traceEntry.result = safeValue(result);
      recordSessionHiUtilsTrace(traceEntry, "verification");
      return {available:true,ok:Boolean(result && result.ret),result};
    } catch (e) {
      traceEntry.error = errorText(e);
      recordSessionHiUtilsTrace(traceEntry, "verification");
      return {available:true,ok:false,error:errorText(e)};
    }
  }

  function maybeParseJsonString(value) {
    if (typeof value !== "string") return null;
    const text = value.trim();
    if (!text || !((text.startsWith("{") && text.endsWith("}")) || (text.startsWith("[") && text.endsWith("]")))) return null;
    try { return JSON.parse(text); } catch (_) { return null; }
  }

  function dataPropertyEntries(record) {
    if (!record || typeof record !== "object") return [];
    let names = [];
    try { names = Object.getOwnPropertyNames(record); } catch (_) { return []; }
    const entries = [];
    for (const name of names.slice(0, SERIALIZE_LIMITS.maxPropertiesPerObject)) {
      try {
        const descriptor = Object.getOwnPropertyDescriptor(record, name);
        if (descriptor && Object.prototype.hasOwnProperty.call(descriptor, "value")) {
          entries.push([name, descriptor.value]);
        }
      } catch (_) {}
    }
    return entries;
  }

  function pickField(record, names) {
    const entries = dataPropertyEntries(record);
    if (!entries.length) return null;
    const lookup = {};
    for (const [key, value] of entries) lookup[key.toLowerCase()] = value;
    for (const name of names) {
      const value = lookup[name.toLowerCase()];
      if (value !== undefined && value !== null && value !== "") return value;
    }
    return null;
  }

  function recordMatchesTarget(record, target) {
    const values = [
      pickField(record, ["id","appId","applicationId","packageId"]),
      pickField(record, ["name","appName","title"]),
      pickField(record, ["url","appUrl","startCommand","startUrl"])
    ].filter((value) => value !== null).map((value) => String(value).toLowerCase());
    const needles = [target.app_id, target.app_name, target.app_url]
      .filter(Boolean).map((value) => String(value).toLowerCase());
    return needles.some((needle) => values.some((value) => value.includes(needle)));
  }

  function compactAppRecord(record, target) {
    const compact = {
      id:pickField(record, ["id","appId","applicationId","packageId"]),
      name:pickField(record, ["name","appName","title","AppName","Title"]),
      url:pickField(record, ["url","appUrl","URL","startUrl"]),
      startCommand:pickField(record, ["startCommand","StartCommand","command"]),
      storeType:pickField(record, ["storeType","StoreType","type"]),
      matchedTarget:recordMatchesTarget(record, target)
    };
    const version = pickField(record, ["version","appVersion","Version"]);
    if (version !== null) compact.version = version;
    const packageName = pickField(record, ["packageName","package","pkg"]);
    if (packageName !== null) compact.packageName = packageName;
    return safeValue(compact);
  }

  function collectAppRecords(value, target) {
    const result = [];
    const dedupe = new Set();
    const queue = [value];
    let visited = 0;

    while (queue.length && visited < PROBE_LIMITS.maxEntries && result.length < SERIALIZE_LIMITS.maxArrayItems) {
      let current = queue.shift();
      visited += 1;
      const parsed = maybeParseJsonString(current);
      if (parsed !== null) current = parsed;
      if (current === null || current === undefined) continue;
      if (Array.isArray(current)) {
        current.slice(0, SERIALIZE_LIMITS.maxArrayItems).forEach((item) => queue.push(item));
        continue;
      }
      if (typeof current !== "object") continue;

      const hasIdentity =
        pickField(current, ["id","appId","applicationId","packageId"]) !== null ||
        pickField(current, ["name","appName","title","AppName","Title"]) !== null ||
        pickField(current, ["url","appUrl","URL","startCommand","StartCommand"]) !== null;

      if (hasIdentity) {
        const compact = compactAppRecord(current, target);
        const key = safeJson([compact.id,compact.name,compact.url,compact.startCommand,compact.storeType]);
        if (!dedupe.has(key)) {
          dedupe.add(key);
          result.push(compact);
        }
      } else {
        for (const [, child] of dataPropertyEntries(current)) {
          if (child !== null && (typeof child === "object" || typeof child === "string")) queue.push(child);
        }
      }
    }
    return result;
  }

  function compactInstalledApps(raw, target) {
    const apps = collectAppRecords(raw, target);
    return {
      available:Boolean(raw && raw.available),
      ok:Boolean(raw && raw.ok),
      callbackTimedOut:Boolean(raw && raw.callbackTimedOut),
      count:apps.length,
      apps
    };
  }

  function compactAppInfo(raw, target) {
    const apps = collectAppRecords(raw, target);
    return {
      available:Boolean(raw && raw.available),
      ok:Boolean(raw && raw.ok),
      skipped:Boolean(raw && raw.skipped),
      count:apps.length,
      apps
    };
  }

  function verificationReference(result) {
    return {
      timestamp:result.timestamp,
      verified:result.verified,
      evidence:result.evidence,
      installedAppsCount:result.installedApps.count,
      appInfoCount:result.appInfo.count
    };
  }

  async function verify(deep, options) {
    const opts = options || {};
    const target = currentTarget();
    syncTargetToReport();
    const installedAppsRaw = await callInstalledApps();
    const appInfoRaw = deep ? readAppInfo() : {available:typeof window.HiUtils_createRequest === "function",skipped:true};

    const phase = opts.snapshot || ((state.report.installDiagnostic.attempts || []).length ? "after" : "before");
    if (phase === "before" || phase === "after") {
      const replaceSnapshot = opts.replaceSnapshot === true || phase === "after";
      captureRawSnapshot("installedApps" + (phase === "before" ? "Before" : "After"), installedAppsRaw, replaceSnapshot);
      if (deep) captureRawSnapshot("appInfo" + (phase === "before" ? "Before" : "After"), appInfoRaw, replaceSnapshot);
    }

    const installedApps = compactInstalledApps(installedAppsRaw, target);
    const appInfo = compactAppInfo(appInfoRaw, target);
    const verifiedByInstalledApps = installedApps.apps.some((app) => app.matchedTarget);
    const verifiedByAppInfo = appInfo.apps.some((app) => app.matchedTarget);
    const result = {
      timestamp:new Date().toISOString(),
      deep:Boolean(deep),
      installedApps,
      appInfo,
      verified:Boolean(verifiedByInstalledApps || verifiedByAppInfo),
      evidence:verifiedByInstalledApps ? "Hisense_getInstalledApps" : verifiedByAppInfo ? "websdk/Appinfo.json" : null
    };

    state.report.verification = safeValue(result);
    state.report.summary.getInstalledAppsAvailable = installedApps.available;
    if (deep && appInfo.available) state.report.summary.appInfoReadable = appInfo.ok;
    state.report.summary.verification = result.verified ? STATUS.VERIFIED_INSTALLED : STATUS.NOT_INSTALLED;
    if (result.verified) state.report.summary.conclusion = "VERIFIED INSTALLED";

    $("verifyOutput").textContent =
      (result.verified ? STATUS.VERIFIED_INSTALLED : STATUS.NOT_INSTALLED) +
      " · Installed apps: " + installedApps.count +
      (deep ? " · Appinfo: " + appInfo.count : "") +
      (result.evidence ? " · Evidence: " + result.evidence : "");
    renderSummary();
    if (opts.log !== false) {
      log(result.verified
        ? "Verification — target found via " + result.evidence
        : "Verification — target not found");
    }
    if (opts.autosave !== false) await saveReport("verification");
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

  function validateInstallTarget() {
    const target = currentTarget();
    if (!target.app_id || !target.app_name || !target.app_url) {
      setInstallState("App ID, name and URL are required.", "bad");
      return null;
    }
    return target;
  }

  function installMethodLabel(method) {
    return method === "v2" ? "V2 install" : "Legacy install";
  }

  function setInstallControlsDisabled(disabled) {
    ["installDiagnosticBtn","installLegacyBtn","installV2Btn","uninstallBtn"].forEach((id) => {
      const el = $(id);
      if (el) el.disabled = Boolean(disabled);
    });
  }

  async function runInstallAttempt(method) {
    const target = currentTarget();
    const isV2 = method === "v2";
    const apiName = isV2 ? "Hisense_installApp_V2" : "Hisense_installApp";
    const api = window[apiName];
    const icon = resolveIconUrl(target);
    const attempt = {
      timestamp:new Date().toISOString(),
      method,
      api:apiName,
      target:{...target, resolved_icon_url:icon || null},
      requested:false,
      callback:null,
      returnValue:null,
      refresh:null,
      verification:null,
      hiUtilsTrace:[],
      classification:STATUS.UNKNOWN,
      clientContextBefore:captureTraceClientContext(),
      clientContextAfter:null
    };
    state.report.installDiagnostic.attempts.push(attempt);

    if (typeof api !== "function") {
      attempt.unavailable = true;
      attempt.clientContextAfter = captureTraceClientContext();
      attempt.completedAt = new Date().toISOString();
      return attempt;
    }
    if (!icon) {
      attempt.error = "A valid icon URL is required.";
      attempt.clientContextAfter = captureTraceClientContext();
      attempt.completedAt = new Date().toISOString();
      return attempt;
    }

    if ($("iconUrl").value.trim() !== icon) $("iconUrl").value = icon;
    syncTargetToReport();
    setInstallState(installMethodLabel(method) + " — requesting…", "warn");

    return await new Promise((resolve) => {
      const restoreTrace = beginHiUtilsTrace(attempt);
      let settled = false;
      let timer = null;

      const finish = () => {
        if (settled) return;
        settled = true;
        if (timer) clearTimeout(timer);
        restoreTrace();
        attempt.clientContextAfter = captureTraceClientContext();
        attempt.completedAt = new Date().toISOString();
        resolve(attempt);
      };

      const callback = function (code) {
        if (settled) return;
        attempt.callback = {code:safeValue(code),receivedAt:new Date().toISOString()};
        attempt.refresh = refreshLauncher(target.app_id);
        if (timer) clearTimeout(timer);
        timer = setTimeout(finish, 1500);
      };

      try {
        attempt.requested = true;
        if (isV2) {
          const appInfo = buildV2AppInfo(target, icon);
          attempt.v2Payload = safeValue(appInfo);
          attempt.returnValue = safeValue(api(appInfo, callback));
        } else {
          attempt.returnValue = safeValue(api(
            target.app_id, target.app_name,
            icon, icon, icon,
            target.app_url, target.store_type || "store",
            callback
          ));
        }
        timer = setTimeout(() => {
          attempt.callbackTimeout = true;
          finish();
        }, 5000);
      } catch (error) {
        attempt.error = errorText(error);
        finish();
      }
    });
  }

  function logAttemptResult(attempt) {
    const details = installTraceDetails(attempt);
    const codeSuffix =
      details.errorCode !== null && details.errorCode !== undefined
        ? " (" + details.errorCode + ")"
        : "";
    log(installMethodLabel(attempt.method) + " — " + String(attempt.classification || STATUS.UNKNOWN).toLowerCase() + codeSuffix);
  }

  async function verifyAttempt(attempt) {
    const verification = await verify(true, {
      snapshot:"after",
      replaceSnapshot:true,
      autosave:false,
      log:false
    });
    attempt.verification = verificationReference(verification);
    updateInstallSummary(attempt, verification);
    logAttemptResult(attempt);
    log(verification.verified ? "Verification — target found" : "Verification — target not found");
    return verification;
  }

  async function runInstallDiagnostic() {
    if (diagnosticRunning) return;
    if (!validateInstallTarget()) return;

    diagnosticRunning = true;
    setInstallControlsDisabled(true);
    try {
      state.report.installDiagnostic = {
        startedAt:new Date().toISOString(),
        status:STATUS.REQUESTED,
        attempts:[]
      };
      Object.assign(state.report.summary, {
        installRequest:STATUS.REQUESTED,
        internalReason:STATUS.UNKNOWN,
        permissionCode:STATUS.UNKNOWN,
        verification:STATUS.UNKNOWN,
        conclusion:STATUS.REQUESTED
      });
      renderSummary();

      setInstallState("Snapshot before install diagnostic…", "warn");
      const baseline = await verify(true, {
        snapshot:"before",
        replaceSnapshot:true,
        autosave:false,
        log:false
      });
      state.report.installDiagnostic.before = verificationReference(baseline);
      await saveReport("install-diagnostic-before");

      const legacyAttempt = await runInstallAttempt("legacy");
      const legacyVerification = await verifyAttempt(legacyAttempt);
      await saveReport("install-diagnostic-legacy");

      const v2Attempt = await runInstallAttempt("v2");
      const v2Verification = await verifyAttempt(v2Attempt);

      const verified = Boolean(legacyVerification.verified || v2Verification.verified);
      const attempts = state.report.installDiagnostic.attempts;
      const anyRejected = attempts.some((attempt) => attempt.classification === STATUS.REJECTED);
      const anyRequested = attempts.some((attempt) => attempt.classification === STATUS.REQUESTED);
      const finalStatus = verified
        ? STATUS.VERIFIED_INSTALLED
        : anyRejected
          ? STATUS.REJECTED
          : anyRequested
            ? STATUS.REQUESTED
            : STATUS.UNKNOWN;

      state.report.installDiagnostic.status = finalStatus;
      state.report.installDiagnostic.completedAt = new Date().toISOString();
      state.report.installDiagnostic.finalVerification = verificationReference(v2Verification);
      state.report.summary.installRequest = finalStatus;
      state.report.summary.verification = verified ? STATUS.VERIFIED_INSTALLED : STATUS.NOT_INSTALLED;
      state.report.summary.conclusion = verified ? STATUS.VERIFIED_INSTALLED : finalStatus;
      renderSummary();

      if (verified) {
        setInstallState("VERIFIED INSTALLED — target found by verification.", "good");
      } else if (finalStatus === STATUS.REJECTED) {
        setInstallState("REJECTED — install request failed. See Summary for the internal reason.", "bad");
      } else {
        setInstallState("Diagnostic complete — target is NOT INSTALLED.", "warn");
      }
      await saveReport("install-diagnostic");
    } finally {
      diagnosticRunning = false;
      setInstallControlsDisabled(false);
    }
  }

  async function runAdvancedInstall(method) {
    if (diagnosticRunning) return;
    if (!validateInstallTarget()) return;

    diagnosticRunning = true;
    setInstallControlsDisabled(true);
    try {
      if (!state.report.installDiagnostic || !Array.isArray(state.report.installDiagnostic.attempts)) {
        state.report.installDiagnostic = {status:STATUS.UNKNOWN,attempts:[]};
      }
      const baseline = await verify(true, {
        snapshot:"before",
        replaceSnapshot:true,
        autosave:false,
        log:false
      });
      const attempt = await runInstallAttempt(method);
      attempt.before = verificationReference(baseline);
      await verifyAttempt(attempt);
      state.report.installDiagnostic.status = attempt.classification;
      state.report.installDiagnostic.completedAt = new Date().toISOString();
      await saveReport("advanced-" + method + "-diagnostic");
    } finally {
      diagnosticRunning = false;
      setInstallControlsDisabled(false);
    }
  }

  async function install() {
    return runAdvancedInstall("legacy");
  }

  async function installV2() {
    return runAdvancedInstall("v2");
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
        const result = await verify(true, {snapshot:"after",autosave:false});
        state.report.installDiagnostic.uninstall = {
          timestamp:new Date().toISOString(),
          callbackStatus:safeValue(status),
          verification:verificationReference(result)
        };
        setInstallState(result.verified ? "Uninstall callback returned, but the app is still visible to verification." : "App is no longer visible to Sidee verification.", result.verified ? "warn" : "good");
        await saveReport("uninstall");
      });
    } catch (e) {
      setInstallState("Uninstall call threw: " + String(e && e.message || e), "bad");
    }
  }

  function buildSessionReport() {
    syncTargetToReport();
    state.report.updatedAt = new Date().toISOString();
    try {
      return JSON.parse(JSON.stringify(state.report));
    } catch (_) {
      return {
        sessionId:state.report.sessionId,
        startedAt:state.report.startedAt,
        updatedAt:state.report.updatedAt,
        summary:safeValue(state.report.summary),
        environment:safeValue(state.report.environment),
        permissionProbe:safeValue(state.report.permissionProbe),
        clientIdentityProbe:safeValue(state.report.clientIdentityProbe),
        target:safeValue(state.report.target),
        installDiagnostic:safeValue(state.report.installDiagnostic),
        verification:safeValue(state.report.verification),
        hiUtilsTrace:safeValue(state.report.hiUtilsTrace),
        raw:{snapshots:safeValue(state.report.raw.snapshots)}
      };
    }
  }

  async function persistReport(reason) {
    const report = buildSessionReport();
    const payload = {sessionId:report.sessionId, report};
    try {
      const r = await fetch("/api/reports/session", {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify(payload)
      });
      const data = await r.json();
      if (!r.ok || !data.ok) throw new Error(data.error || ("HTTP " + r.status));
      const reportName = $("reportFileName");
      if (reportName) reportName.textContent = data.file || currentReportFileName();
      const saveState = $("reportSaveState");
      if (saveState) saveState.textContent = reason === "export" ? "Report exported/synced." : "Session autosaved.";
      if (reason === "export") log("Export Report — " + data.file);
      return data;
    } catch (e) {
      const saveState = $("reportSaveState");
      if (saveState) saveState.textContent = "Report save failed: " + errorText(e);
      log("Could not save session report.", {reason,error:errorText(e)});
      return {ok:false,error:errorText(e)};
    }
  }

  function saveReport(reason) {
    reportSaveChain = reportSaveChain
      .catch(() => null)
      .then(() => persistReport(reason));
    return reportSaveChain;
  }

  $("scanBtn").addEventListener("click", scan);
  $("permissionProbeBtn").addEventListener("click", permissionProbe);
  $("clientIdentityProbeBtn").addEventListener("click", clientIdentityProbe);
  $("saveBtn").addEventListener("click", saveTarget);
  $("verifyBtn").addEventListener("click", () => verify(true));
  $("installDiagnosticBtn").addEventListener("click", runInstallDiagnostic);
  $("installLegacyBtn").addEventListener("click", install);
  $("installV2Btn").addEventListener("click", installV2);
  $("uninstallBtn").addEventListener("click", uninstall);
  $("reportBtn").addEventListener("click", () => saveReport("export"));

  function isVisibleFocusable(element) {
    if (!element || element.disabled) return false;
    const style = window.getComputedStyle(element);
    return style.display !== "none" && style.visibility !== "hidden" && element.getClientRects().length > 0;
  }

  function focusableControls() {
    return Array.from(document.querySelectorAll("button,input,summary"))
      .filter(isVisibleFocusable);
  }

  function elementCenter(element) {
    const rect = element.getBoundingClientRect();
    return {x:rect.left + rect.width / 2, y:rect.top + rect.height / 2};
  }

  function spatialTarget(current, key, candidates) {
    const from = elementCenter(current);
    let best = null;
    let bestScore = Infinity;

    for (const candidate of candidates) {
      if (candidate === current) continue;
      const to = elementCenter(candidate);
      const dx = to.x - from.x;
      const dy = to.y - from.y;
      let primary = 0;
      let cross = 0;

      if (key === "ArrowUp") {
        if (dy >= -4) continue;
        primary = -dy;
        cross = Math.abs(dx);
      } else if (key === "ArrowDown") {
        if (dy <= 4) continue;
        primary = dy;
        cross = Math.abs(dx);
      } else if (key === "ArrowLeft") {
        if (dx >= -4) continue;
        primary = -dx;
        cross = Math.abs(dy);
      } else if (key === "ArrowRight") {
        if (dx <= 4) continue;
        primary = dx;
        cross = Math.abs(dy);
      }

      const score = primary * 10 + cross;
      if (score < bestScore) {
        best = candidate;
        bestScore = score;
      }
    }
    return best;
  }

  window.addEventListener("keydown", (e) => {
    const key = e.key || ({13:"Enter",37:"ArrowLeft",38:"ArrowUp",39:"ArrowRight",40:"ArrowDown"}[e.keyCode]);
    const active = document.activeElement;

    if ((key === "Enter" || key === "OK") && active && (active.tagName === "BUTTON" || active.tagName === "SUMMARY")) {
      e.preventDefault();
      active.click();
      return;
    }

    if (!["ArrowUp","ArrowDown","ArrowLeft","ArrowRight"].includes(key)) return;
    if (active && active.tagName === "INPUT" && (key === "ArrowLeft" || key === "ArrowRight")) return;

    const controls = focusableControls();
    if (!controls.length) return;
    const current = controls.includes(active) ? active : controls[0];
    const target = spatialTarget(current, key, controls);
    if (target) {
      target.focus();
      e.preventDefault();
    } else if (!controls.includes(active)) {
      current.focus();
      e.preventDefault();
    }
  });

  getConfig().then(() => {
    syncTargetToReport();
    renderSummary();
    log("Sidee UI ready — " + currentReportFileName());
    $("deviceBadge").textContent = typeof window.Hisense_GetFirmWareVersion === "function" ? "VIDAA browser detected" : "Waiting for VIDAA APIs";
  }).catch((e)=>log("Config load failed.",String(e)));
})();
