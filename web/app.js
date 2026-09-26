(() => {
  "use strict";

  const $ = id => document.getElementById(id);
  const SESSION_RE = /^sidee-\d{8}-\d{6}-[a-f0-9]{4}$/;
  const CLIENT_KEYS = /(app|identifier|appid|role|customer|origin|url|permission|appconfig|store|package|security)/i;
  const logBox = $("console");
  const state = { config:null, report:null, running:false, saveChain:Promise.resolve() };

  function err(e){ return String(e && e.message || e); }
  function cut(v,n){ const s=String(v); return s.length>n?s.slice(0,n)+"…":s; }
  function compact(v,d,seen){
    d=d||0; seen=seen||[];
    if(v===undefined)return "[undefined]";
    if(v===null||typeof v==="boolean"||typeof v==="number")return v;
    if(typeof v==="string")return cut(v,500);
    if(typeof v==="function")return "[function "+(v.name||"anonymous")+"]";
    if(typeof v!=="object")return cut(v,200);
    if(d>=2)return Array.isArray(v)?"[array]":"[object]";
    if(seen.indexOf(v)>=0)return "[circular]";
    seen.push(v);
    const out=Array.isArray(v)?[]:{};
    try{
      const keys=Array.isArray(v)?Object.keys(v).slice(0,20):Object.keys(v).slice(0,30);
      keys.forEach(k=>{ try{ out[k]=compact(v[k],d+1,seen); }catch(e){ out[k]="[read error: "+err(e)+"]"; } });
    }catch(e){}
    seen.pop(); return out;
  }
  function log(msg,data){
    if(!logBox)return;
    let line="["+new Date().toLocaleTimeString()+"] "+msg;
    if(data!==undefined){ try{ line+="\n"+JSON.stringify(compact(data),null,2); }catch(e){} }
    logBox.textContent=line+"\n\n"+logBox.textContent;
    if(logBox.textContent.length>12000)logBox.textContent=logBox.textContent.slice(0,12000);
  }
  function set(id,v){ const el=$(id); if(el)el.textContent=v==null?"—":String(v); }
  function pad(n){ return String(n).padStart(2,"0"); }
  function sessionId(){
    try{ const old=sessionStorage.getItem("sidee.sessionId"); if(old&&SESSION_RE.test(old))return old; }catch(e){}
    const d=new Date(), stamp=d.getFullYear()+pad(d.getMonth()+1)+pad(d.getDate())+"-"+pad(d.getHours())+pad(d.getMinutes())+pad(d.getSeconds());
    let tail=Math.floor(Math.random()*65536).toString(16).padStart(4,"0");
    try{ const a=new Uint8Array(2); crypto.getRandomValues(a); tail=Array.from(a).map(x=>x.toString(16).padStart(2,"0")).join(""); }catch(e){}
    const id="sidee-"+stamp+"-"+tail; try{sessionStorage.setItem("sidee.sessionId",id);}catch(e){} return id;
  }
  function newReport(){ const now=new Date().toISOString(); return {sessionId:sessionId(),startedAt:now,updatedAt:now,device:{},baseline:null,contextInit:{status:"NOT_RUN",available:false,before:null,after:null,diff:null},clientInformation:null,serviceTrace:[],installTest:null,verification:null,target:{},summary:{runtimeIdentity:"MISSING",contextInit:"NOT_RUN",permissionGate:"UNKNOWN"}}; }
  state.report=newReport();

  function meaningful(v){
    if(v==null)return false;
    if(typeof v==="string"){ const s=v.trim().toLowerCase(); return !!s&&s!=="undefined"&&s!=="[undefined]"&&s!=="null"&&s!=="[null]"; }
    return true;
  }
  function prop(root,name){
    if(!root)return {status:"UNAVAILABLE",value:null};
    try{ return {status:"RETURNED",value:compact(root[name])}; }catch(e){ return {status:"ERROR",value:null,error:err(e)}; }
  }
  function call(root,name){
    if(!root)return {status:"UNAVAILABLE",value:null};
    let fn; try{fn=root[name];}catch(e){return {status:"ERROR",value:null,error:err(e)};}
    if(typeof fn!=="function")return {status:"UNAVAILABLE",value:null};
    try{return {status:"RETURNED",value:compact(fn.call(root))};}catch(e){return {status:"ERROR",value:null,error:err(e)};}
  }
  function descriptor(root,name){
    let cur=root;
    for(let depth=0;cur&&depth<6;depth++){
      try{ const d=Object.getOwnPropertyDescriptor(cur,name); if(d)return {found:true,ownerDepth:depth,enumerable:!!d.enumerable,configurable:!!d.configurable,writable:Object.prototype.hasOwnProperty.call(d,"writable")?!!d.writable:null,hasGetter:typeof d.get==="function",hasSetter:typeof d.set==="function"}; cur=Object.getPrototypeOf(cur); }
      catch(e){return {found:false,error:err(e)};}
    }
    return {found:false};
  }
  function clientInfo(){
    const out={timestamp:new Date().toISOString(),descriptor:descriptor(window,"clientInformation"),status:"UNAVAILABLE",type:"missing",value:null,error:null,setterUsed:false};
    try{
      const v=window.clientInformation; out.status="RETURNED"; out.type=v===null?"null":typeof v; out.sameAsNavigator=v===navigator;
      if(v&&["object","function"].indexOf(typeof v)>=0){
        const picked={}; let names=[]; try{names=Object.getOwnPropertyNames(v);}catch(e){}
        names.filter(n=>CLIENT_KEYS.test(n)).slice(0,30).forEach(n=>{try{picked[n]=compact(v[n]);}catch(e){picked[n]="[read error]";}});
        out.value=Object.keys(picked).length?picked:{type:Object.prototype.toString.call(v),sameAsNavigator:out.sameAsNavigator};
      }else out.value=compact(v);
    }catch(e){out.status="ERROR";out.type="error";out.error=err(e);}
    return out;
  }
  function capture(label){
    let service=null,ctx=null; try{service=window.vowOS&&window.vowOS.service;}catch(e){} try{ctx=window.vowOSContext;}catch(e){}
    return {label:label||null,timestamp:new Date().toISOString(),navigatorAppIdentifier:prop(navigator,"appIdentifier"),serviceIdentifier:call(service,"getIdentifier"),appIdentifier:call(ctx,"getAppIdentifier"),appId:call(ctx,"getAppId"),roleId:call(window,"Hisense_GetRoleID"),customerId:call(window,"Hisense_GetCustomerID"),roleSetterAvailable:typeof window.Hisense_SetRoleID==="function",customerSetterAvailable:typeof window.Hisense_SetCustomerID==="function",clientInformation:clientInfo()};
  }
  function identityStatus(s){
    if(!s)return "MISSING";
    const core=[s.navigatorAppIdentifier,s.serviceIdentifier,s.appIdentifier,s.appId];
    if(core.some(x=>x&&x.status==="RETURNED"&&meaningful(x.value)))return "PRESENT";
    if([s.roleId,s.customerId].some(x=>x&&x.status==="RETURNED"&&meaningful(x.value)))return "PARTIAL";
    return "MISSING";
  }
  function display(x){ if(!x||x.status==="UNAVAILABLE")return "UNAVAILABLE"; if(x.status==="ERROR")return "ERROR"; if(!meaningful(x.value))return "EMPTY"; return typeof x.value==="string"?cut(x.value,80):cut(JSON.stringify(x.value),80); }
  function diff(a,b){
    const changed=k=>JSON.stringify(a&&a[k]?a[k].value:null)!==JSON.stringify(b&&b[k]?b[k].value:null);
    return {appIdentifierChanged:changed("navigatorAppIdentifier")||changed("appIdentifier"),appIdChanged:changed("appId"),serviceIdentifierChanged:changed("serviceIdentifier"),roleChanged:changed("roleId"),customerChanged:changed("customerId"),clientInformationChanged:JSON.stringify(a&&a.clientInformation&&a.clientInformation.value)!==JSON.stringify(b&&b.clientInformation&&b.clientInformation.value)};
  }
  function current(){ return state.report.contextInit&&state.report.contextInit.after||state.report.baseline; }
  function renderIdentity(s){ s=s||{}; set("navigatorAppIdentifierValue",display(s.navigatorAppIdentifier)); set("serviceIdentifierValue",display(s.serviceIdentifier)); set("appIdentifierValue",display(s.appIdentifier)); set("appIdValue",display(s.appId)); set("roleIdValue",display(s.roleId)); set("customerIdValue",display(s.customerId)); set("roleSetterValue",s.roleSetterAvailable?"YES":"NO"); set("customerSetterValue",s.customerSetterAvailable?"YES":"NO"); }
  function renderSummary(){ state.report.summary.runtimeIdentity=identityStatus(current()); set("summaryRuntimeIdentity",state.report.summary.runtimeIdentity); set("summaryContextInit",state.report.summary.contextInit); set("summaryPermissionGate",state.report.summary.permissionGate); set("summaryIdentifier",current()?display(current().serviceIdentifier):"UNKNOWN"); set("reportFileName","sidee-session-"+state.report.sessionId.slice(6)+".json"); }
  function renderDiff(d){ if(!d)return set("contextDiff","No comparison yet."); set("contextDiff",[["App identifier",d.appIdentifierChanged],["App ID",d.appIdChanged],["Service identifier",d.serviceIdentifierChanged],["Role",d.roleChanged],["Customer",d.customerChanged],["Client information",d.clientInformationChanged]].map(x=>x[0]+": "+(x[1]?"CHANGED":"NO CHANGE")).join(" · ")); }
  function getter(name){ try{const fn=window[name]; return typeof fn==="function"?compact(fn()):null;}catch(e){return null;} }
  function device(){ return {firmware:getter("Hisense_GetFirmWareVersion"),os:getter("Hisense_GetOSVersion"),api:getter("Hisense_GetApiVersion"),browser:getter("Hisense_GetCurrentBrowser")||navigator.userAgent,chipset:getter("Hisense_GetChipSetName"),model:getter("Hisense_GetModelName"),origin:location.origin}; }

  async function baseline(){ state.report.device=device(); state.report.baseline=capture("baseline"); state.report.clientInformation=state.report.baseline.clientInformation; renderIdentity(state.report.baseline); renderSummary(); set("baselineState","Baseline captured."); set("deviceBadge",state.report.device.firmware?"VIDAA runtime detected":"VIDAA APIs not detected"); log("Baseline captured",{runtimeIdentity:state.report.summary.runtimeIdentity,serviceIdentifier:display(state.report.baseline.serviceIdentifier),appIdentifier:display(state.report.baseline.appIdentifier),appId:display(state.report.baseline.appId)}); await save("baseline"); }
  function timeout(ms,label){ return new Promise((_,reject)=>setTimeout(()=>reject(new Error((label||"Operation")+" timed out after "+ms+" ms")),ms)); }
  async function invokeInit(fn,ctx){
    let src=""; try{src=Function.prototype.toString.call(fn);}catch(e){}
    const wantsCb=fn.length===1||/\b(callback|cb|done|complete)\b/i.test(src); let cbCalled=false,cbValue=null,resolveCb;
    const cbPromise=new Promise(resolve=>{resolveCb=resolve;});
    const cb=function(){cbCalled=true;cbValue=compact(Array.prototype.slice.call(arguments));resolveCb(cbValue);};
    const ret=wantsCb?fn.call(ctx,cb):fn.call(ctx); let value=compact(ret);
    if(ret&&typeof ret.then==="function")value=compact(await Promise.race([Promise.resolve(ret),timeout(2500,"vowOSContext.init promise")]));
    else if(wantsCb&&ret===undefined){try{await Promise.race([cbPromise,timeout(1800,"vowOSContext.init callback")]);}catch(e){}}
    return {callbackSuggested:wantsCb,callbackCalled:cbCalled,callbackValue:cbValue,returnType:ret===null?"null":typeof ret,returnValue:value};
  }
  async function initContext(){
    if(state.running)return; state.running=true; set("contextState","Initializing runtime context…");
    const before=capture("beforeInit"); let ctx=null,fn=null,result=null,error=null;
    try{ctx=window.vowOSContext;fn=ctx&&ctx.init;}catch(e){error=err(e);}
    if(!error&&typeof fn!=="function")error="vowOSContext.init is unavailable";
    if(!error){try{result=await Promise.race([invokeInit(fn,ctx),timeout(3000,"vowOSContext.init")]);}catch(e){error=err(e);}}
    const after=capture("afterInit"), d=diff(before,after), status=error?"ERROR":Object.keys(d).some(k=>d[k])?"IDENTITY_CHANGED":"NO_CHANGE";
    state.report.contextInit={status:status,available:typeof fn==="function",timestamp:new Date().toISOString(),call:result,error:error,before:before,after:after,diff:d}; state.report.clientInformation=after.clientInformation; state.report.summary.contextInit=status;
    renderIdentity(after); renderDiff(d); renderSummary(); set("contextState",error?"Init completed with error: "+error:"Runtime context completed: "+status); log("vowOSContext.init completed",{status:status,error:error,diff:d}); state.running=false; await save("context-init");
  }
  async function readClient(){ const r=clientInfo(); state.report.clientInformation=r; const s=current(); if(s)s.clientInformation=r; set("clientInformationState",r.status+" · type "+r.type+(typeof r.sameAsNavigator==="boolean"?" · sameAsNavigator "+(r.sameAsNavigator?"YES":"NO"):"")+(r.value&&typeof r.value==="object"?" · keys: "+Object.keys(r.value).join(", "):"")); log("clientInformation read",r); await save("client-information"); }

  function traceResult(v){
    const out={ret:null,code:null,msg:null},q=[v],seen=[]; let n=0;
    while(q.length&&n++<80&&(out.ret===null||out.code===null||out.msg===null)){const x=q.shift();if(!x||typeof x!=="object"||seen.indexOf(x)>=0)continue;seen.push(x);Object.keys(x).slice(0,25).forEach(k=>{let y;try{y=x[k];}catch(e){return;}const l=k.toLowerCase();if(out.ret===null&&l==="ret")out.ret=compact(y);if(out.code===null&&(l==="code"||l==="errorcode"))out.code=compact(y);if(out.msg===null&&(l==="msg"||l==="message"||l==="error"))out.msg=cut(y,300);if(y&&typeof y==="object")q.push(y);});}
    return out;
  }
  async function traced(source,operation){
    const t={timestamp:new Date().toISOString(),source:source,service:null,api:null,identifier:null,endpoint:null,payload:null,result:null,errors:[]}; let svc=null,origId=null,origSync=null,origHi=null,origOpen=null;
    function restore(){if(svc&&origId)try{svc.getIdentifier=origId;}catch(e){} if(svc&&origSync)try{svc.syncExecute=origSync;}catch(e){} if(origHi)try{window.HiUtils_createRequest=origHi;}catch(e){} if(origOpen&&window.XMLHttpRequest&&window.XMLHttpRequest.prototype)try{window.XMLHttpRequest.prototype.open=origOpen;}catch(e){}}
    try{
      try{svc=window.vowOS&&window.vowOS.service;}catch(e){}
      if(svc&&typeof svc.getIdentifier==="function"){origId=svc.getIdentifier;try{svc.getIdentifier=function(){const v=origId.apply(this,arguments);t.identifier=compact(v);return v;};}catch(e){t.errors.push("getIdentifier wrap: "+err(e));}}
      if(svc&&typeof svc.syncExecute==="function"){origSync=svc.syncExecute;try{svc.syncExecute=function(){const a=Array.prototype.slice.call(arguments);if(t.service===null&&a.length)t.service=compact(a[0]);const v=origSync.apply(this,arguments);if(!t.result)t.result=traceResult(v);return v;};}catch(e){t.errors.push("syncExecute wrap: "+err(e));}}
      if(typeof window.HiUtils_createRequest==="function"){origHi=window.HiUtils_createRequest;try{window.HiUtils_createRequest=function(type,msg){t.service="hiutils";t.api=String(type);t.payload=compact(msg);if(t.identifier===null&&svc&&typeof svc.getIdentifier==="function")try{t.identifier=compact(svc.getIdentifier());}catch(e){}const v=origHi.apply(this,arguments);t.result=traceResult(v);return v;};}catch(e){t.errors.push("HiUtils wrap: "+err(e));}}
      if(window.XMLHttpRequest&&window.XMLHttpRequest.prototype&&typeof window.XMLHttpRequest.prototype.open==="function"){origOpen=window.XMLHttpRequest.prototype.open;try{window.XMLHttpRequest.prototype.open=function(m,u){if(typeof u==="string"&&/localhost:(9888|9009)\/service\//i.test(u))t.endpoint=u;return origOpen.apply(this,arguments);};}catch(e){t.errors.push("XHR wrap: "+err(e));}}
      const v=await operation(t); if(!t.result)t.result=traceResult(v); return {value:v,trace:t};
    }catch(e){t.errors.push("operation: "+err(e));return {value:null,error:err(e),trace:t};}
    finally{restore();state.report.serviceTrace.push(t);if(state.report.serviceTrace.length>20)state.report.serviceTrace.splice(0,state.report.serviceTrace.length-20);}
  }
  async function readTrace(){ if(typeof window.HiUtils_createRequest!=="function")return set("serviceTraceState","HiUtils_createRequest unavailable."); const r=await traced("readonly-appinfo",()=>window.HiUtils_createRequest("fileRead",{path:"websdk/Appinfo.json",mode:6})); set("serviceTraceState","api "+(r.trace.api||"unknown")+" · identifier "+(meaningful(r.trace.identifier)?String(r.trace.identifier):"EMPTY")+" · code "+(r.trace.result&&r.trace.result.code!==null?r.trace.result.code:"—")); log("Read-only service trace",r.trace); await save("readonly-service-trace"); }

  function target(){ return {app_id:$("appId").value.trim(),app_name:$("appName").value.trim(),app_url:$("appUrl").value.trim(),icon_url:$("iconUrl").value.trim(),store_type:state.config&&state.config.nuvio&&state.config.nuvio.store_type||"store"}; }
  function icon(t){ if(t.icon_url)return t.icon_url; try{return new URL("/assets/images/icon.png",t.app_url).toString();}catch(e){return "";} }
  function v2(t){const i=icon(t);return {Id:t.app_id,appId:t.app_id,AppName:t.app_name,name:t.app_name,Title:t.app_name,URL:t.app_url,url:t.app_url,StartCommand:t.app_url,Thumb:i,Icon_96:i,Image:i,IconURL:i,icon:i,StoreType:t.store_type||"store",storeType:t.store_type||"store",PreInstall:false,isShowOnLauncher:true};}
  function wait(ms){return new Promise(r=>setTimeout(r,ms));}
  async function installCall(method){
    const t=target(),isV2=method==="v2",fn=isV2?window.Hisense_installApp_V2:window.Hisense_installApp,rec={timestamp:new Date().toISOString(),method:method,identifierSnapshot:capture("installTest"),payload:null,returnValue:null,externalCallback:null,error:null};
    if(typeof fn!=="function"){rec.error="Install API unavailable";return rec;}
    let resolveCb;const cbp=new Promise(r=>resolveCb=r),cb=s=>{rec.externalCallback=compact(s);resolveCb(s);};
    const tr=await traced("install-"+method,async()=>{try{if(isV2){const p=v2(t);rec.payload=compact(p);rec.returnValue=compact(fn(p,cb));}else{const i=icon(t);rec.payload={appId:t.app_id,appName:t.app_name,icon:i,url:t.app_url,storeType:t.store_type||"store"};rec.returnValue=compact(fn(t.app_id,t.app_name,i,i,i,t.app_url,t.store_type||"store",cb));}try{await Promise.race([cbp,timeout(4000,"install callback")]);}catch(e){}return rec.returnValue;}catch(e){rec.error=err(e);throw e;}});
    rec.trace=tr.trace;if(tr.error&&!rec.error)rec.error=tr.error;return rec;
  }
  function parseJson(v){if(typeof v!=="string")return null;const s=v.trim();if(!s||"[{".indexOf(s[0])<0)return null;try{return JSON.parse(s);}catch(e){return null;}}
  function collect(v,out,d){if(d>3||out.length>=80||v==null)return;const p=parseJson(v);if(p)return collect(p,out,d+1);if(Array.isArray(v)){v.slice(0,50).forEach(x=>collect(x,out,d+1));return;}if(typeof v!=="object")return;out.push(v);Object.keys(v).slice(0,30).forEach(k=>{try{const c=v[k],j=parseJson(c);if(j)collect(j,out,d+1);else if(c&&typeof c==="object")collect(c,out,d+1);}catch(e){}});}
  function matches(r,t){const needles=[t.app_id,t.app_name,t.app_url].filter(Boolean).map(x=>String(x).toLowerCase());const vals=[];try{Object.keys(r).slice(0,30).forEach(k=>{const v=r[k];if(typeof v==="string"||typeof v==="number")vals.push(String(v).toLowerCase());});}catch(e){}return needles.some(n=>vals.some(v=>v.indexOf(n)>=0));}
  async function installed(){if(typeof window.Hisense_getInstalledApps!=="function")return {available:false,match:false};let resolveCb;const cbp=new Promise(r=>resolveCb=r);let ret;try{ret=window.Hisense_getInstalledApps(function(){resolveCb(Array.prototype.slice.call(arguments));});}catch(e){return {available:true,match:false,error:err(e)};}const cb=await Promise.race([cbp,wait(1200).then(()=>null)]),records=[];collect(ret,records,0);collect(cb,records,0);const t=target();return {available:true,match:records.some(r=>matches(r,t)),count:records.length};}
  function appInfo(){if(typeof window.HiUtils_createRequest!=="function")return {available:false,match:false};try{const raw=window.HiUtils_createRequest("fileRead",{path:"websdk/Appinfo.json",mode:6}),records=[];collect(raw,records,0);const t=target();return {available:true,ok:!!(raw&&raw.ret),match:records.some(r=>matches(r,t)),count:records.length};}catch(e){return {available:true,match:false,error:err(e)};}}
  async function verify(){const a=await installed(),b=appInfo(),r={timestamp:new Date().toISOString(),installedApps:a,appInfo:b,verified:!!(a.match||b.match)};state.report.verification=r;set("verifyOutput",r.verified?"VERIFIED INSTALLED":"NOT INSTALLED");return r;}
  function gate(test,verification,previous){const i=test&&test.trace&&test.trace.result||{},code=i.code,ret=i.ret,msg=String(i.msg||"");if(verification&&verification.verified)return "PASSED";if(Number(code)===503&&/permission|appconfig/i.test(msg))return "REJECTED";if(ret===true)return "PASSED";if(previous&&previous.internal&&(previous.internal.code!==code||previous.internal.ret!==ret))return "CHANGED";return "UNKNOWN";}
  async function installTest(method){
    if(state.running)return;const t=target();if(!t.app_id||!t.app_name||!t.app_url)return set("installState","App ID, name and URL are required.");state.running=true;set("installState","Running explicit install permission test…");const prev=state.report.installTest,chosen=method||(typeof window.Hisense_installApp_V2==="function"?"v2":"legacy"),test=await installCall(chosen),verification=await verify(),internal=test.trace&&test.trace.result||{ret:null,code:null,msg:null},status=gate(test,verification,prev);
    state.report.installTest={timestamp:test.timestamp,method:chosen,identifierUsed:test.trace?test.trace.identifier:null,appIdentifier:test.identifierSnapshot.appIdentifier,appId:test.identifierSnapshot.appId,roleId:test.identifierSnapshot.roleId,customerId:test.identifierSnapshot.customerId,payload:test.payload,returnValue:test.returnValue,internal:internal,externalCallback:test.externalCallback,error:test.error,verification:verification};state.report.summary.permissionGate=status;renderSummary();set("installState",status+" · internal ret "+String(internal.ret)+" · code "+String(internal.code)+" · callback "+String(test.externalCallback)+" · "+(verification.verified?"verified installed":"not installed"));log("Install permission test",state.report.installTest);state.running=false;await save("install-permission-test");
  }
  async function tempIdentifier(){
    const value=$("temporaryIdentifier").value.trim();if(!value)return set("temporaryIdentifierState","Enter an identifier first. No test was run.");let svc=null;try{svc=window.vowOS&&window.vowOS.service;}catch(e){}if(!svc||typeof svc.getIdentifier!=="function")return set("temporaryIdentifierState","vowOS.service.getIdentifier is unavailable.");const original=svc.getIdentifier;let r=null;
    try{svc.getIdentifier=function(){return value;};r=await traced("temporary-identifier-readonly",()=>{if(typeof window.HiUtils_createRequest!=="function")throw new Error("HiUtils_createRequest unavailable");return window.HiUtils_createRequest("fileRead",{path:"websdk/Appinfo.json",mode:6});});set("temporaryIdentifierState","Test complete · identifier "+value+" · code "+String(r.trace.result&&r.trace.result.code));log("Temporary Identifier Test complete and restored",r.trace);}catch(e){set("temporaryIdentifierState","Test error: "+err(e));}finally{try{svc.getIdentifier=original;}catch(e){}}await save("temporary-identifier-test");
  }

  function syncTarget(){state.report.target=compact(target());}
  async function saveTarget(){syncTarget();try{const r=await fetch("/api/config",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({nuvio:target()})}),d=await r.json();if(!r.ok||!d.ok)throw new Error(d.error||"Could not save target");state.config.nuvio=d.nuvio;set("targetState","Target saved.");await save("target");}catch(e){set("targetState","Save failed: "+err(e));}}
  async function persist(reason){syncTarget();state.report.updatedAt=new Date().toISOString();try{const r=await fetch("/api/reports/session",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({sessionId:state.report.sessionId,report:state.report})}),d=await r.json();if(!r.ok||!d.ok)throw new Error(d.error||"Report save failed");set("reportFileName",d.file);set("reportSaveState",reason==="export"?"Report exported/synced.":"Session autosaved.");return d;}catch(e){set("reportSaveState","Report save failed: "+err(e));return {ok:false,error:err(e)};}}
  function save(reason){state.saveChain=state.saveChain.catch(()=>null).then(()=>persist(reason));return state.saveChain;}
  async function load(){const r=await fetch("/api/config",{cache:"no-store"}),d=await r.json();state.config=d;const a=d.nuvio||{};$("appId").value=a.app_id||"nuviodebug";$("appName").value=a.app_name||"Nuvio TV";$("appUrl").value=a.app_url||"";$("iconUrl").value=a.icon_url||"";syncTarget();}

  function controls(){return Array.prototype.slice.call(document.querySelectorAll("button,input,summary")).filter(el=>{if(!el||el.disabled||el.hidden)return false;const s=getComputedStyle(el);return s.display!=="none"&&s.visibility!=="hidden"&&el.getClientRects().length>0;});}
  function center(el){const r=el.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2};}
  function nextControl(cur,key,list){const from=center(cur);let best=null,score=Infinity;list.forEach(el=>{if(el===cur)return;const to=center(el),dx=to.x-from.x,dy=to.y-from.y;let p=null,c=0;if(key==="ArrowUp"&&dy<-4){p=-dy;c=Math.abs(dx);}if(key==="ArrowDown"&&dy>4){p=dy;c=Math.abs(dx);}if(key==="ArrowLeft"&&dx<-4){p=-dx;c=Math.abs(dy);}if(key==="ArrowRight"&&dx>4){p=dx;c=Math.abs(dy);}if(p===null)return;const s=p*10+c;if(s<score){score=s;best=el;}});return best;}
  window.addEventListener("keydown",e=>{const key=e.key||({13:"Enter",37:"ArrowLeft",38:"ArrowUp",39:"ArrowRight",40:"ArrowDown"}[e.keyCode]),active=document.activeElement;if((key==="Enter"||key==="OK")&&active&&(active.tagName==="BUTTON"||active.tagName==="SUMMARY")){e.preventDefault();active.click();return;}if(["ArrowUp","ArrowDown","ArrowLeft","ArrowRight"].indexOf(key)<0)return;if(active&&active.tagName==="INPUT"&&(key==="ArrowLeft"||key==="ArrowRight"))return;const list=controls();if(!list.length)return;const cur=list.indexOf(active)>=0?active:list[0],to=nextControl(cur,key,list);if(to){to.focus();e.preventDefault();}else if(list.indexOf(active)<0){cur.focus();e.preventDefault();}});

  $("baselineBtn").addEventListener("click",baseline); $("runtimeContextInitBtn").addEventListener("click",initContext); $("clientInformationBtn").addEventListener("click",readClient); $("serviceTraceBtn").addEventListener("click",readTrace); $("installDiagnosticBtn").addEventListener("click",()=>installTest()); $("installLegacyBtn").addEventListener("click",()=>installTest("legacy")); $("installV2Btn").addEventListener("click",()=>installTest("v2")); $("temporaryIdentifierBtn").addEventListener("click",tempIdentifier); $("saveBtn").addEventListener("click",saveTarget); $("verifyBtn").addEventListener("click",async()=>{const r=await verify();log("Verification",r);await save("verification");}); $("reportBtn").addEventListener("click",()=>save("export"));
  load().then(()=>{renderSummary();set("deviceBadge",typeof window.Hisense_GetFirmWareVersion==="function"?"VIDAA browser detected":"Waiting for VIDAA APIs");log("Sidee targeted identity diagnostic ready.");}).catch(e=>log("Config load failed",err(e)));
})();
