(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const logBox = $("console");
  const state = {
    config: null,
    scan: null,
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
    "HiUtils_createRequest","omi_platform","opera_omi"
  ];

  const SAFE_GETTERS = [
    "Hisense_GetApiVersion","Hisense_GetDeviceInfo","Hisense_GetChromiumVersion",
    "Hisense_GetCurrentBrowser","Hisense_GetFirmWareVersion","Hisense_GetDeviceCode",
    "Hisense_GetChipSetName","Hisense_GetOSVersion","Hisense_GetCountryCode",
    "Hisense_GetRegion","Hisense_GetPanelResolution","Hisense_GetIPAddress",
    "Hisense_GetFeatureCode","Hisense_GetCapabilityCode","Hisense_GetBrand",
    "Hisense_GetModelName","Hisense_GetTestApiList"
  ];

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

  function currentTarget() {
    return {
      app_id: $("appId").value.trim(),
      app_name: $("appName").value.trim(),
      app_url: $("appUrl").value.trim(),
      icon_url: $("iconUrl").value.trim(),
      store_type: state.config?.nuvio?.store_type || "store"
    };
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
      try { Object.getOwnPropertyNames(cursor).forEach((n) => names.add(n)); } catch (_) {}
      try { cursor = Object.getPrototypeOf(cursor); } catch (_) { break; }
    }
    const matcher = /(hisense|vidaa|hiutils|omi|install|uninstall|appinfo|file(read|write)|debug|api(version|list)|platform)/i;
    return Array.from(names).filter((name) => matcher.test(name)).sort().map((name) => {
      let value;
      try { value = window[name]; } catch (e) { return {name, type:"blocked", error:String(e)}; }
      let source = null;
      if (typeof value === "function") {
        try { source = Function.prototype.toString.call(value).slice(0, 1200); } catch (_) {}
      }
      return {name, type:typeof value, available:value !== undefined && value !== null, source};
    });
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
        const ret = fn(function () {
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

  async function install() {
    const target = currentTarget();
    if (!target.app_id || !target.app_name || !target.app_url) {
      setInstallState("App ID, name and URL are required.", "bad");
      return;
    }
    if (typeof window.Hisense_installApp !== "function") {
      setInstallState("Hisense_installApp is not available in this browser context.", "bad");
      log("Install API unavailable.");
      return;
    }

    setInstallState("Calling Hisense_installApp…", "warn");
    const icon = target.icon_url || target.app_url;
    const attempt = {timestamp:new Date().toISOString(),target,callback:null,refresh:null,verification:null};
    state.installAttempts.push(attempt);

    try {
      window.Hisense_installApp(
        target.app_id, target.app_name,
        icon, icon, icon,
        target.app_url, target.store_type || "store",
        async function (code) {
          attempt.callback = {code:safeValue(code),receivedAt:new Date().toISOString()};
          log("Hisense_installApp callback.", attempt.callback);
          attempt.refresh = refreshLauncher(target.app_id);
          await new Promise((r)=>setTimeout(r,1500));
          attempt.verification = await verify(true);
          if (attempt.verification.verified) {
            setInstallState("Verified: Nuvio is present (" + attempt.verification.evidence + "). Restart the TV if the launcher has not refreshed yet.", "good");
          } else if (Number(code) === 0) {
            setInstallState("VIDAA returned code 0, but Sidee could NOT verify the app. Request accepted ≠ installed.", "warn");
          } else {
            setInstallState("VIDAA install callback returned: " + String(code) + ".", "bad");
          }
          await saveReport("install");
        }
      );
    } catch (e) {
      attempt.error = String(e && e.message || e);
      setInstallState("Install call threw: " + attempt.error, "bad");
      log("Install exception.", attempt);
      await saveReport("install-error");
    }
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
  $("saveBtn").addEventListener("click", saveTarget);
  $("verifyBtn").addEventListener("click", () => verify(false));
  $("deepBtn").addEventListener("click", () => verify(true));
  $("installBtn").addEventListener("click", install);
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
