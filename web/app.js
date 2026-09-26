(() => {
  "use strict";

  const $ = id => document.getElementById(id);
  const CLIENT_BUILD_ID = (() => {
    try {
      const src = document.currentScript && document.currentScript.src;
      if (!src) return "unversioned";
      const value = new URL(src, location.href).searchParams.get("v");
      return value || "unversioned";
    } catch (e) { return "unversioned"; }
  })();
  const SESSION_RE = /^sidee-\d{8}-\d{6}-[a-f0-9]{4}$/;
  const CLIENT_KEYS = /(app|identifier|appid|role|customer|origin|url|permission|appconfig|store|package|security)/i;
  const CONTEXT_IDENTITY_KEYS = /(app.?config|permission|capabilit|privileg|identifier|app.?id|client|context|role|customer|origin|domain|host|package|bundle|store|vendor|launcher|browser|profile)/i;
  const CONTEXT_SENSITIVE_KEYS = /(token|secret|password|cookie|credential|authorization|\bauth\b|private|\bkey\b|certificate|signature|nonce|session)/i;
  const logBox = $("console");
  const state = { config:null, report:null, running:false, saveChain:Promise.resolve(), syncWatchToken:0, remoteDiagnosticArmed:false, remoteDiagnosticRunning:false, remoteDiagnosticTimer:null };

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
  function newReport(){ const now=new Date().toISOString(); return {sessionId:sessionId(),clientBuildId:CLIENT_BUILD_ID,serverBuildId:null,buildMatch:null,startedAt:now,updatedAt:now,accessContext:pageContext(),accessMode:accessMode(),serverAccess:null,device:{},baseline:null,contextInit:{status:"NOT_RUN",available:false,before:null,after:null,diff:null},contextIdentityFingerprint:null,clientInformation:null,serviceTrace:[],permissionSourceTrace:null,installTest:null,verification:null,installedAppMetadata:null,target:{},temporaryIdentifierTest:null,identityOverrideLab:null,identityWriteGateLab:null,candidatePermissionTest:null,directAppInfoWriteLab:null,legacyHspdkWriteLab:null,summary:{runtimeIdentity:"MISSING",contextInit:"NOT_RUN",contextFingerprint:"NOT_RUN",permissionGate:"UNKNOWN",appInfoWrite:"NOT_RUN"}}; }
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
  function expectedInstalledAppContext(){
    const host=String(location.hostname||"").toLowerCase();
    if(host==="vidaa.smartone-iptv.com")return {id:"1470",name:"Smartone IPTV",host:host,mode:"SMARTONE_APP_CONTEXT"};
    if(host==="vidaa.duplecast.com")return {id:"1876",name:"Duplecast",host:host,mode:"DUPLECAST_APP_CONTEXT"};
    return null;
  }
  function primitiveIdentityPreview(value,name){
    const sensitive=CONTEXT_SENSITIVE_KEYS.test(String(name||""));
    const type=value===null?"null":typeof value;
    if(sensitive)return {type:type,redacted:true,value:"[redacted by Sidee]"};
    if(value===null||["string","number","boolean"].indexOf(type)>=0)return {type:type,redacted:false,value:compact(value)};
    return {type:type,redacted:false,value:null};
  }
  function shallowIdentityObject(value,path,depth,seen){
    depth=depth||0;seen=seen||[];
    if(!value||typeof value!=="object"||depth>1||seen.indexOf(value)>=0)return null;
    seen.push(value);
    const out={},names=[];
    let props=[];try{props=Object.getOwnPropertyNames(value);}catch(e){seen.pop();return {error:err(e)};}
    for(let i=0;i<props.length&&names.length<40;i++){
      const name=props[i];
      let d=null;try{d=Object.getOwnPropertyDescriptor(value,name);}catch(e){}
      if(!d||!Object.prototype.hasOwnProperty.call(d,"value"))continue;
      const child=d.value,childType=child===null?"null":typeof child;
      if(CONTEXT_SENSITIVE_KEYS.test(name)){out[name]={type:childType,redacted:true,value:"[redacted by Sidee]"};names.push(name);continue;}
      if(child===null||["string","number","boolean"].indexOf(childType)>=0){out[name]=compact(child);names.push(name);continue;}
      if(depth===0&&child&&childType==="object"&&CONTEXT_IDENTITY_KEYS.test(name)){
        out[name]=shallowIdentityObject(child,path+"."+name,depth+1,seen);names.push(name);
      }
    }
    seen.pop();
    return out;
  }
  function inspectIdentityDataOwner(owner,path,limit){
    const out={path:path,available:!!owner,propertyCount:0,matches:[],error:null};
    if(!owner)return out;
    let names=[];try{names=Object.getOwnPropertyNames(owner);}catch(e){out.error=err(e);return out;}
    out.propertyCount=names.length;
    for(let i=0;i<names.length&&i<(limit||120);i++){
      const name=names[i];
      if(!CONTEXT_IDENTITY_KEYS.test(name))continue;
      let d=null;try{d=Object.getOwnPropertyDescriptor(owner,name);}catch(e){out.matches.push({name:name,error:err(e)});continue;}
      if(!d)continue;
      const rec={name:name,path:path+"."+name,enumerable:!!d.enumerable,configurable:!!d.configurable,writable:Object.prototype.hasOwnProperty.call(d,"writable")?!!d.writable:null,hasGetter:typeof d.get==="function",hasSetter:typeof d.set==="function",kind:Object.prototype.hasOwnProperty.call(d,"value")?"data":"accessor",type:null,value:null,preview:null,redacted:false};
      if(Object.prototype.hasOwnProperty.call(d,"value")){
        const v=d.value;rec.type=v===null?"null":typeof v;
        if(CONTEXT_SENSITIVE_KEYS.test(name)){rec.redacted=true;rec.value="[redacted by Sidee]";}
        else if(v===null||["string","number","boolean"].indexOf(typeof v)>=0)rec.value=compact(v);
        else if(v&&typeof v==="object")rec.preview=shallowIdentityObject(v,rec.path,0,[]);
        else if(typeof v==="function"){rec.functionName=v.name||null;rec.functionLength=v.length;rec.references=sourceReferences(functionSource(v)).slice(0,30);}
      }
      out.matches.push(rec);
      if(out.matches.length>=50)break;
    }
    return out;
  }
  function identityExpectedMatches(identity,expected){
    if(!expected)return [];
    const fields=["navigatorAppIdentifier","serviceIdentifier","appIdentifier","appId"],out=[];
    fields.forEach(name=>{
      const item=identity&&identity[name],value=item&&item.status==="RETURNED"?item.value:null;
      out.push({field:name,value:meaningful(value)?compact(value):null,matchesExpected:String(value==null?"":value).trim()===String(expected.id)});
    });
    return out;
  }
  function contextFingerprintClassification(identity,expected,owners,support){
    const core=[identity&&identity.navigatorAppIdentifier,identity&&identity.serviceIdentifier,identity&&identity.appIdentifier,identity&&identity.appId];
    const hasCore=core.some(x=>x&&x.status==="RETURNED"&&meaningful(x.value));
    const matchesExpected=identityExpectedMatches(identity,expected).some(x=>x.matchesExpected);
    const metadataHits=(owners||[]).reduce((n,x)=>n+(x&&x.matches?x.matches.length:0),0);
    if(expected&&matchesExpected)return "INSTALLED_APP_IDENTITY_MATCH";
    if(expected&&hasCore)return "INSTALLED_APP_IDENTITY_PRESENT";
    if(expected&&metadataHits>0)return "INSTALLED_APP_METADATA_PRESENT";
    if(expected)return "INSTALLED_APP_CONTEXT_ANONYMOUS";
    if(hasCore)return "BROWSER_IDENTITY_PRESENT";
    if(support&&support.status==="RETURNED"&&meaningful(support.value))return "APPCONFIG_SIGNAL_ONLY";
    return "ANONYMOUS_LIKE";
  }
  function renderContextIdentityFingerprint(r){
    set("contextFingerprintExpected",r&&r.expectedContext?(r.expectedContext.name+" · "+r.expectedContext.id):"none");
    set("contextFingerprintIdentity",r&&r.identity?identityStatus(r.identity):"MISSING");
    set("contextFingerprintMatch",r&&r.expectedMatches?(r.expectedMatches.some(x=>x.matchesExpected)?"YES":"NO"):"—");
    set("contextFingerprintAppConfig",r&&r.supportAppConfig?display(r.supportAppConfig):"UNAVAILABLE");
    set("contextFingerprintMetadata",r&&r.metadataHitCount!=null?r.metadataHitCount:"0");
    set("contextFingerprintConclusion",r&&r.classification?r.classification:"NOT_RUN");
    set("contextIdentityFingerprintState",r?(r.classification+" · "+(r.automatic?"automatic app-context capture":"manual read-only capture")):"Not run yet.");
    state.report.summary.contextFingerprint=r&&r.classification||"NOT_RUN";
    renderSummary();
  }
  async function contextIdentityFingerprint(options){
    if(state.running)return null;
    state.running=true;
    set("contextIdentityFingerprintState","Capturing read-only native client context…");
    const automatic=!!(options&&options.automatic);
    let service=null,ctx=null;try{service=window.vowOS&&window.vowOS.service;}catch(e){}try{ctx=window.vowOSContext;}catch(e){}
    const identity=capture("contextIdentityFingerprint");
    let support={status:"UNAVAILABLE",value:null};
    try{support=call(window,"Hisense_SupportAppConfig");}catch(e){support={status:"ERROR",value:null,error:err(e)};}
    const owners=[
      inspectIdentityDataOwner(service,"window.vowOS.service",180),
      inspectIdentityDataOwner(ctx,"window.vowOSContext",180),
      inspectIdentityDataOwner(navigator,"window.navigator",180),
      inspectIdentityDataOwner(window,"window",1200)
    ];
    const expected=expectedInstalledAppContext(),matches=identityExpectedMatches(identity,expected);
    const metadataHitCount=owners.reduce((n,x)=>n+(x.matches?x.matches.length:0),0);
    const report={timestamp:new Date().toISOString(),automatic:automatic,remote:!!(options&&options.remote),pageContext:pageContext(),expectedContext:expected,identity:identity,expectedMatches:matches,supportAppConfig:support,owners:owners,metadataHitCount:metadataHitCount,classification:contextFingerprintClassification(identity,expected,owners,support),safety:"Read-only descriptor/data-property inspection only. Unknown accessors are not invoked. Token/secret/auth/cookie/key/signature/session-like fields are redacted."};
    state.report.contextIdentityFingerprint=report;
    if(!state.report.baseline){state.report.baseline=identity;state.report.clientInformation=identity.clientInformation;renderIdentity(identity);}
    state.report.summary.runtimeIdentity=identityStatus(identity);
    renderContextIdentityFingerprint(report);
    log("Context identity fingerprint", {classification:report.classification,mode:pageContext().accessMode,expected:expected,identity:identityStatus(identity),metadataHitCount:metadataHitCount});
    state.running=false;
    await save("context-identity-fingerprint");
    return report;
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
  function renderSummary(){ state.report.summary.runtimeIdentity=identityStatus(current()); set("summaryRuntimeIdentity",state.report.summary.runtimeIdentity); set("summaryContextInit",state.report.summary.contextInit); set("summaryContextFingerprint",state.report.summary.contextFingerprint||"NOT_RUN"); set("summaryPermissionGate",state.report.summary.permissionGate); set("summaryAppInfoWrite",state.report.summary.appInfoWrite||"NOT_RUN"); set("summaryIdentifier",current()?display(current().serviceIdentifier):"UNKNOWN"); set("summaryAccessOrigin",location.origin); set("summaryAccessMode",accessMode()); set("reportFileName","sidee-session-"+state.report.sessionId.slice(6)+".json"); }
  function renderDiff(d){ if(!d)return set("contextDiff","No comparison yet."); set("contextDiff",[["App identifier",d.appIdentifierChanged],["App ID",d.appIdChanged],["Service identifier",d.serviceIdentifierChanged],["Role",d.roleChanged],["Customer",d.customerChanged],["Client information",d.clientInformationChanged]].map(x=>x[0]+": "+(x[1]?"CHANGED":"NO CHANGE")).join(" · ")); }
  function getter(name){ try{const fn=window[name]; return typeof fn==="function"?compact(fn()):null;}catch(e){return null;} }
  function accessMode(){
    const host=String(location.hostname||"").toLowerCase();
    if(host==="vidaa.smartone-iptv.com")return "SMARTONE_APP_CONTEXT";
    if(host==="vidaa.duplecast.com")return "DUPLECAST_APP_CONTEXT";
    if(host==="vidaahub.com"||host==="www.vidaahub.com")return "VIDAAHUB_BROWSER_CONTEXT";
    if(/^\d{1,3}(?:\.\d{1,3}){3}$/.test(host))return "RAW_IP_BROWSER_CONTEXT";
    return "OTHER_CONTEXT";
  }
  function pageContext(){ return {href:location.href,origin:location.origin,protocol:location.protocol,hostname:location.hostname,port:location.port||("https:"===location.protocol?"443":"http:"===location.protocol?"80":""),host:location.host,secureContext:window.isSecureContext===true,accessMode:accessMode()}; }
  function device(){ return {firmware:getter("Hisense_GetFirmWareVersion"),os:getter("Hisense_GetOSVersion"),api:getter("Hisense_GetApiVersion"),browser:getter("Hisense_GetCurrentBrowser")||navigator.userAgent,chipset:getter("Hisense_GetChipSetName"),model:getter("Hisense_GetModelName"),origin:location.origin,pageContext:pageContext()}; }

  async function baseline(){ state.report.device=device(); state.report.baseline=capture("baseline"); state.report.clientInformation=state.report.baseline.clientInformation; renderIdentity(state.report.baseline); renderSummary(); set("baselineState","Baseline captured."); set("deviceBadge",state.report.device.firmware?"VIDAA runtime detected":"VIDAA APIs not detected"); log("Baseline captured",{runtimeIdentity:state.report.summary.runtimeIdentity,serviceIdentifier:display(state.report.baseline.serviceIdentifier),appIdentifier:display(state.report.baseline.appIdentifier),appId:display(state.report.baseline.appId)}); await save("baseline"); }
  function withTimeout(promise,ms,label){ return new Promise((resolve,reject)=>{ let done=false; const timer=setTimeout(()=>{if(done)return;done=true;reject(new Error((label||"Operation")+" timed out after "+ms+" ms"));},ms); Promise.resolve(promise).then(v=>{if(done)return;done=true;clearTimeout(timer);resolve(v);},e=>{if(done)return;done=true;clearTimeout(timer);reject(e);}); }); }
  async function invokeInit(fn,ctx){
    let src=""; try{src=Function.prototype.toString.call(fn);}catch(e){}
    const wantsCb=fn.length===1||/\b(callback|cb|done|complete)\b/i.test(src); let cbCalled=false,cbValue=null,resolveCb;
    const cbPromise=new Promise(resolve=>{resolveCb=resolve;});
    const cb=function(){cbCalled=true;cbValue=compact(Array.prototype.slice.call(arguments));resolveCb(cbValue);};
    const ret=wantsCb?fn.call(ctx,cb):fn.call(ctx); let value=compact(ret);
    if(ret&&typeof ret.then==="function")value=compact(await withTimeout(Promise.resolve(ret),2500,"vowOSContext.init promise"));
    else if(wantsCb&&ret===undefined){try{await withTimeout(cbPromise,1800,"vowOSContext.init callback");}catch(e){}}
    return {callbackSuggested:wantsCb,callbackCalled:cbCalled,callbackValue:cbValue,returnType:ret===null?"null":typeof ret,returnValue:value};
  }
  async function initContext(){
    if(state.running)return; state.running=true; set("contextState","Initializing runtime context…");
    const before=capture("beforeInit"); let ctx=null,fn=null,result=null,error=null;
    try{ctx=window.vowOSContext;fn=ctx&&ctx.init;}catch(e){error=err(e);}
    if(!error&&typeof fn!=="function")error="vowOSContext.init is unavailable";
    if(!error){try{result=await withTimeout(invokeInit(fn,ctx),3000,"vowOSContext.init");}catch(e){error=err(e);}}
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

  const SOURCE_TRACE_RE=/(permission|appconfig|identifier|client|role|customer|origin|package|bundle|auth|security|sign|certificate|access|capability|privilege|config|installapplication|hiutils|syncexecute|getidentifier|executehttprequest|filewrite|fileread|appinfo|writeinstallappobjtojson|getinstalledappjsonobj|mapappinfofields)/i;
  function functionSource(fn){
    if(typeof fn!=="function")return null;
    try{return Function.prototype.toString.call(fn);}catch(e){return "[source error: "+err(e)+"]";}
  }
  function sourceReferences(src){
    if(!src)return [];
    const found={},out=[];
    const add=v=>{v=String(v||"").trim();if(!v||!SOURCE_TRACE_RE.test(v)||found[v])return;found[v]=true;if(out.length<100)out.push(cut(v,300));};
    const quoted=/["']([^"'\\]{1,300})["']/g;let m;
    while((m=quoted.exec(src))&&out.length<100)add(m[1]);
    const words=/\b[A-Za-z_$][\w$\.]{2,120}\b/g;
    while((m=words.exec(src))&&out.length<100)add(m[0]);
    return out;
  }
  function inspectFunction(owner,name,path){
    const out={path:path||name,available:false,descriptor:descriptor(owner,name),type:"missing",name:null,length:null,source:null,references:[],error:null};
    let fn;try{fn=owner&&owner[name];}catch(e){out.type="error";out.error=err(e);return out;}
    out.type=fn===null?"null":typeof fn;if(typeof fn!=="function")return out;
    out.available=true;out.name=fn.name||null;out.length=fn.length;out.source=functionSource(fn);out.references=sourceReferences(out.source);return out;
  }

  const SCRIPT_SOURCE_TERMS=["mapAppInfoFields","appIdentifier","getAppIdentifier","AppConfig","permission","identifier","client","service","vowOSContext","getIdentifier","executeHttpRequest","installApplication","HiUtils_createRequest"];
  function scriptSourceHits(source){
    const text=String(source||""),lower=text.toLowerCase(),hits=[],excerpts=[],seen={};
    SCRIPT_SOURCE_TERMS.forEach(term=>{
      const needle=term.toLowerCase();let from=0,found=false,count=0;
      while(count<3){
        const idx=lower.indexOf(needle,from);if(idx<0)break;
        found=true;count++;from=idx+needle.length;
        const key=term+"@"+idx;if(seen[key])continue;seen[key]=true;
        const start=Math.max(0,idx-650),end=Math.min(text.length,idx+needle.length+950);
        excerpts.push({term:term,index:idx,excerpt:text.slice(start,end)});
        if(excerpts.length>=24)break;
      }
      if(found)hits.push(term);
    });
    return {matchedTerms:hits,excerpts:excerpts.slice(0,24)};
  }
  async function loadedScriptSourceTrace(){
    const scripts=Array.prototype.slice.call(document.scripts||[]),entries=[];
    for(let i=0;i<scripts.length&&i<80;i++){
      const el=scripts[i],src=el.src||"",entry={index:i,src:src||null,inline:!src,type:el.type||null,sameOrigin:null,status:"SKIPPED",sourceLength:0,matchedTerms:[],excerpts:[],error:null};
      let source="";
      if(!src){
        try{source=el.textContent||"";entry.status="INLINE";}catch(e){entry.status="ERROR";entry.error=err(e);}
      }else{
        let url=null;try{url=new URL(src,location.href);entry.sameOrigin=url.origin===location.origin;}catch(e){entry.status="ERROR";entry.error=err(e);}
        if(entry.sameOrigin){
          if(url&&(url.pathname==="/app.js"||url.pathname==="/hspdk-context.js")){entry.status="SIDEE_SELF_SKIPPED";}
          else{
            try{
              const response=await withTimeout(fetch(url.href,{cache:"no-store",credentials:"same-origin"}),3000,"script source fetch");
              if(!response.ok)throw new Error("HTTP "+response.status);
              source=await withTimeout(response.text(),3000,"script source body");
              entry.status="FETCHED";
            }catch(e){entry.status="ERROR";entry.error=err(e);}
          }
        }else if(entry.status!=="ERROR")entry.status="CROSS_ORIGIN_SKIPPED";
      }
      if(source){
        entry.sourceLength=source.length;
        const hits=scriptSourceHits(source);entry.matchedTerms=hits.matchedTerms;entry.excerpts=hits.excerpts;
      }
      entries.push(entry);
    }
    const matched=entries.filter(x=>x.matchedTerms.length>0);
    return {timestamp:new Date().toISOString(),readOnly:true,scriptCount:scripts.length,inspectedCount:entries.filter(x=>x.status==="FETCHED"||x.status==="INLINE").length,matchedScriptCount:matched.length,mapAppInfoFieldsFound:matched.some(x=>x.matchedTerms.indexOf("mapAppInfoFields")>=0),entries:entries};
  }

  const RUNTIME_IDENTITY_NAME_RE=/(app|identifier|client|config|permission|context|role|customer|auth|security|service|origin)/i;
  function richDescriptor(root,name){
    let cur=root;
    for(let depth=0;cur&&depth<7;depth++){
      try{
        const d=Object.getOwnPropertyDescriptor(cur,name);
        if(d){
          const out={found:true,ownerDepth:depth,enumerable:!!d.enumerable,configurable:!!d.configurable,writable:Object.prototype.hasOwnProperty.call(d,"writable")?!!d.writable:null,hasGetter:typeof d.get==="function",hasSetter:typeof d.set==="function",valueType:Object.prototype.hasOwnProperty.call(d,"value")?(d.value===null?"null":typeof d.value):"accessor",value:null,functionSource:null,getterSource:null,setterSource:null,error:null};
          if(Object.prototype.hasOwnProperty.call(d,"value")){
            if(typeof d.value==="function")out.functionSource=functionSource(d.value);
            else if(d.value===null||["string","number","boolean","undefined"].indexOf(typeof d.value)>=0)out.value=compact(d.value);
          }
          if(typeof d.get==="function")out.getterSource=functionSource(d.get);
          if(typeof d.set==="function")out.setterSource=functionSource(d.set);
          return out;
        }
        cur=Object.getPrototypeOf(cur);
      }catch(e){return {found:false,error:err(e)};}
    }
    return {found:false};
  }
  function filteredRuntimeSurface(root,label){
    const out={label:label,available:!!root,levels:[],matchingProperties:[],error:null};
    if(!root)return out;
    let cur=root,seenNames={};
    for(let depth=0;cur&&depth<7;depth++){
      let names=[];try{names=Object.getOwnPropertyNames(cur);}catch(e){out.error=err(e);break;}
      const matched=names.filter(n=>RUNTIME_IDENTITY_NAME_RE.test(n)).slice(0,80);
      const level={depth:depth,type:null,matchingNames:matched};
      try{level.type=Object.prototype.toString.call(cur);}catch(e){}
      out.levels.push(level);
      matched.forEach(name=>{
        const key=name.toLowerCase();if(seenNames[key])return;seenNames[key]=true;
        const d=richDescriptor(root,name);
        out.matchingProperties.push({name:name,descriptor:d});
      });
      try{cur=Object.getPrototypeOf(cur);}catch(e){break;}
    }
    return out;
  }
  function runtimeIdentitySurfaceTrace(){
    let ctx=null,service=null;try{ctx=window.vowOSContext;}catch(e){}try{service=window.vowOS&&window.vowOS.service;}catch(e){}
    const exact={
      navigatorAppIdentifier:richDescriptor(navigator,"appIdentifier"),
      vowOSContextGetAppIdentifier:richDescriptor(ctx,"getAppIdentifier"),
      vowOSContextGetAppId:richDescriptor(ctx,"getAppId"),
      vowOSContextInit:richDescriptor(ctx,"init"),
      vowOSServiceGetIdentifier:richDescriptor(service,"getIdentifier")
    };
    return {timestamp:new Date().toISOString(),readOnly:true,exact:exact,surfaces:{vowOSContext:filteredRuntimeSurface(ctx,"window.vowOSContext"),vowOSService:filteredRuntimeSurface(service,"window.vowOS.service")},notes:["Descriptors and function/getter/setter source are inspected without invoking getters, setters, init methods or discovered functions.","Only scalar data-descriptor values are copied; object values are not traversed except through their own/prototype property names."]};
  }
  function ownDescriptorSnapshot(owner,name,depth){
    try{
      const d=Object.getOwnPropertyDescriptor(owner,name);
      if(!d)return {name:name,ownerDepth:depth,found:false};
      const out={name:name,ownerDepth:depth,found:true,enumerable:!!d.enumerable,configurable:!!d.configurable,writable:Object.prototype.hasOwnProperty.call(d,"writable")?!!d.writable:null,hasGetter:typeof d.get==="function",hasSetter:typeof d.set==="function",valueType:Object.prototype.hasOwnProperty.call(d,"value")?(d.value===null?"null":typeof d.value):"accessor",value:null,functionSource:null,getterSource:null,setterSource:null,error:null};
      if(Object.prototype.hasOwnProperty.call(d,"value")){
        if(typeof d.value==="function")out.functionSource=functionSource(d.value);
        else if(d.value===null||["string","number","boolean","undefined","bigint"].indexOf(typeof d.value)>=0)out.value=compact(d.value);
        else if(Array.isArray(d.value))out.value={type:"array",length:d.value.length};
        else if(typeof d.value==="object"){
          let tag=null;try{tag=Object.prototype.toString.call(d.value);}catch(e){}
          out.value={type:tag||"object"};
        }
      }
      if(typeof d.get==="function")out.getterSource=functionSource(d.get);
      if(typeof d.set==="function")out.setterSource=functionSource(d.set);
      return out;
    }catch(e){return {name:name,ownerDepth:depth,found:false,error:err(e)};}
  }
  function completeRuntimeInventory(root,label){
    const out={label:label,available:!!root,levels:[],propertyCount:0,functionCount:0,getterCount:0,setterCount:0,error:null};
    if(!root)return out;
    let cur=root;
    for(let depth=0;cur&&depth<10;depth++){
      let names=[];try{names=Object.getOwnPropertyNames(cur);}catch(e){out.error=err(e);break;}
      const properties=[];
      for(let i=0;i<names.length&&i<250;i++){
        const item=ownDescriptorSnapshot(cur,names[i],depth);properties.push(item);out.propertyCount++;
        if(item.functionSource)out.functionCount++;if(item.getterSource)out.getterCount++;if(item.setterSource)out.setterCount++;
      }
      let tag=null;try{tag=Object.prototype.toString.call(cur);}catch(e){}
      out.levels.push({depth:depth,type:tag,propertyCount:names.length,truncated:names.length>250,properties:properties});
      try{cur=Object.getPrototypeOf(cur);}catch(e){out.error=err(e);break;}
    }
    return out;
  }
  function runtimeObjectInventoryTrace(){
    let ctx=null,service=null,omi=null;
    try{ctx=window.vowOSContext;}catch(e){}
    try{service=window.vowOS&&window.vowOS.service;}catch(e){}
    try{omi=window.omi_platform;}catch(e){}
    return {timestamp:new Date().toISOString(),readOnly:true,objects:{vowOSContext:completeRuntimeInventory(ctx,"window.vowOSContext"),vowOSService:completeRuntimeInventory(service,"window.vowOS.service"),omiPlatform:completeRuntimeInventory(omi,"window.omi_platform")},notes:["Complete unfiltered property inventory for the three concrete runtime bridge objects, including own properties and prototype levels.","Descriptors and function/getter/setter source are captured without reading accessor values or invoking any discovered function.","Per-level safety cap is 250 property names and prototype traversal cap is 10 levels; truncation is explicitly reported if reached."]};
  }
  const PHOENIX_SOURCE_PATTERNS=[
    {name:"vowOS.service.execute",re:/vowOS\s*\.\s*service\s*\.\s*execute\s*\(/i},
    {name:"phoenixService",re:/phoenix:\/\/service\//i},
    {name:"registerMethod",re:/\bmethod\s*:\s*["']register["']/i},
    {name:"registerAssignment",re:/\.method\s*=\s*["']register["']/i}
  ];
  function phoenixSourceAnalysis(source){
    const text=String(source||""),matched=[];
    PHOENIX_SOURCE_PATTERNS.forEach(p=>{if(p.re.test(text))matched.push(p.name);});
    if(!matched.length)return null;
    const paths=[],seen={};let m;
    const pathRe=/phoenix:\/\/service\/[^"'\x60\s),}]+/gi;
    while((m=pathRe.exec(text))&&paths.length<30){const v=m[0];if(!seen[v]){seen[v]=true;paths.push(v);}}
    const excerpts=[];
    matched.forEach(name=>{
      const p=PHOENIX_SOURCE_PATTERNS.find(x=>x.name===name),match=p&&p.re.exec(text);
      if(match&&excerpts.length<12){
        const idx=match.index,start=Math.max(0,idx-700),end=Math.min(text.length,idx+match[0].length+1200);
        excerpts.push({pattern:name,index:idx,excerpt:text.slice(start,end)});
      }
    });
    return {matchedPatterns:matched,phoenixPaths:paths,excerpts:excerpts};
  }
  function scanFunctionDescriptor(owner,name,path,depth,out,seenFns){
    let d=null;try{d=Object.getOwnPropertyDescriptor(owner,name);}catch(e){return;}
    if(!d||!Object.prototype.hasOwnProperty.call(d,"value")||typeof d.value!=="function")return;
    const fn=d.value;if(seenFns.indexOf(fn)>=0)return;seenFns.push(fn);
    const source=functionSource(fn),analysis=phoenixSourceAnalysis(source);
    out.scannedFunctionCount++;
    if(analysis&&out.matches.length<100)out.matches.push({path:path,ownerDepth:depth,name:name,functionName:fn.name||null,length:fn.length,source:source,matchedPatterns:analysis.matchedPatterns,phoenixPaths:analysis.phoenixPaths,excerpts:analysis.excerpts});
  }
  function globalPhoenixWrapperTrace(){
    const out={timestamp:new Date().toISOString(),readOnly:true,scannedGlobalPropertyCount:0,scannedNamespaceCount:0,scannedFunctionCount:0,matches:[],errors:[],notes:["Scans function source only; no global function, getter, setter, Phoenix service or register call is invoked.","Window data descriptors are inspected directly, so accessor values are not evaluated.","A bounded one-level scan of object-valued global namespaces is included to catch wrappers stored under runtime objects."]};
    const seenFns=[],seenObjects=[];
    let names=[];try{names=Object.getOwnPropertyNames(window);}catch(e){out.errors.push({path:"window",error:err(e)});return out;}
    for(let i=0;i<names.length&&i<1200;i++){
      const name=names[i];out.scannedGlobalPropertyCount++;
      scanFunctionDescriptor(window,name,"window."+name,0,out,seenFns);
      let d=null;try{d=Object.getOwnPropertyDescriptor(window,name);}catch(e){}
      if(!d||!Object.prototype.hasOwnProperty.call(d,"value")||!d.value||typeof d.value!=="object")continue;
      const obj=d.value;
      if(obj===window||obj===document||obj===navigator||seenObjects.indexOf(obj)>=0)continue;
      seenObjects.push(obj);
      let childNames=[];try{childNames=Object.getOwnPropertyNames(obj);}catch(e){continue;}
      if(childNames.length>200)continue;
      out.scannedNamespaceCount++;
      for(let j=0;j<childNames.length&&j<200;j++)scanFunctionDescriptor(obj,childNames[j],"window."+name+"."+childNames[j],1,out,seenFns);
    }
    out.uniquePhoenixPaths=[];
    const pathSeen={};
    out.matches.forEach(x=>(x.phoenixPaths||[]).forEach(v=>{if(!pathSeen[v]){pathSeen[v]=true;out.uniquePhoenixPaths.push(v);}}));
    return out;
  }
  const IDENTITY_USAGE_PATTERNS=[
    {name:"vowOSContext.init",re:/vowOSContext\s*\.\s*init\s*\(/i},
    {name:"vowOSContext.getAppIdentifier",re:/vowOSContext\s*\.\s*getAppIdentifier\s*\(/i},
    {name:"vowOSContext.getAppId",re:/vowOSContext\s*\.\s*getAppId\s*\(/i},
    {name:"navigator.appIdentifier",re:/navigator\s*\.\s*appIdentifier\b/i},
    {name:"getAppIdentifier",re:/\bgetAppIdentifier\s*\(/i},
    {name:"getAppId",re:/\bgetAppId\s*\(/i}
  ];
  function identityUsageAnalysis(source){
    const text=String(source||""),matched=[],excerpts=[];
    IDENTITY_USAGE_PATTERNS.forEach(p=>{
      const m=p.re.exec(text);
      if(!m)return;
      matched.push(p.name);
      if(excerpts.length<16){
        const idx=m.index,start=Math.max(0,idx-750),end=Math.min(text.length,idx+m[0].length+1300);
        excerpts.push({pattern:p.name,index:idx,excerpt:text.slice(start,end)});
      }
    });
    return matched.length?{matchedPatterns:matched,excerpts:excerpts}:null;
  }
  function scanIdentityFunctionDescriptor(owner,name,path,depth,out,seenFns){
    let d=null;try{d=Object.getOwnPropertyDescriptor(owner,name);}catch(e){return;}
    if(!d||!Object.prototype.hasOwnProperty.call(d,"value")||typeof d.value!=="function")return;
    const fn=d.value;if(seenFns.indexOf(fn)>=0)return;seenFns.push(fn);
    const source=functionSource(fn),analysis=identityUsageAnalysis(source);
    out.scannedFunctionCount++;
    if(analysis&&out.matches.length<150)out.matches.push({path:path,ownerDepth:depth,name:name,functionName:fn.name||null,length:fn.length,source:source,matchedPatterns:analysis.matchedPatterns,excerpts:analysis.excerpts});
  }
  function globalIdentityUsageTrace(){
    const out={timestamp:new Date().toISOString(),readOnly:true,scannedGlobalPropertyCount:0,scannedNamespaceCount:0,scannedFunctionCount:0,matches:[],patternCounts:{},errors:[],notes:["Scans existing function source for native identity usage; no function, getter, setter or vowOSContext.init call is invoked.","Window accessors are not evaluated; only data descriptors whose values are already functions/objects are traversed.","A bounded one-level namespace scan mirrors the Phoenix wrapper trace for consistent coverage."]};
    IDENTITY_USAGE_PATTERNS.forEach(p=>out.patternCounts[p.name]=0);
    const seenFns=[],seenObjects=[];
    let names=[];try{names=Object.getOwnPropertyNames(window);}catch(e){out.errors.push({path:"window",error:err(e)});return out;}
    for(let i=0;i<names.length&&i<1200;i++){
      const name=names[i];out.scannedGlobalPropertyCount++;
      scanIdentityFunctionDescriptor(window,name,"window."+name,0,out,seenFns);
      let d=null;try{d=Object.getOwnPropertyDescriptor(window,name);}catch(e){}
      if(!d||!Object.prototype.hasOwnProperty.call(d,"value")||!d.value||typeof d.value!=="object")continue;
      const obj=d.value;
      if(obj===window||obj===document||obj===navigator||seenObjects.indexOf(obj)>=0)continue;
      seenObjects.push(obj);
      let childNames=[];try{childNames=Object.getOwnPropertyNames(obj);}catch(e){continue;}
      if(childNames.length>200)continue;
      out.scannedNamespaceCount++;
      for(let j=0;j<childNames.length&&j<200;j++)scanIdentityFunctionDescriptor(obj,childNames[j],"window."+name+"."+childNames[j],1,out,seenFns);
    }
    out.matches.forEach(x=>(x.matchedPatterns||[]).forEach(p=>{if(Object.prototype.hasOwnProperty.call(out.patternCounts,p))out.patternCounts[p]++;}));
    return out;
  }
  async function permissionSourceTrace(){
    if(state.running)return;state.running=true;set("permissionSourceTraceState","Inspecting function sources and descriptors…");
    try{
      let service=null;try{service=window.vowOS&&window.vowOS.service;}catch(e){}
      const targets=[
        inspectFunction(window,"Hisense_installApp","window.Hisense_installApp"),
        inspectFunction(window,"Hisense_installApp_V2","window.Hisense_installApp_V2"),
        inspectFunction(window,"writeInstallAppObjToJson","window.writeInstallAppObjToJson"),
        inspectFunction(window,"getInstalledAppJsonObj","window.getInstalledAppJsonObj"),
        inspectFunction(window,"mapAppInfoFields","window.mapAppInfoFields"),
        inspectFunction(window,"HiUtils_createRequest","window.HiUtils_createRequest"),
        inspectFunction(window,"Hisense_SupportAppConfig","window.Hisense_SupportAppConfig"),
        inspectFunction(service,"syncExecute","window.vowOS.service.syncExecute"),
        inspectFunction(service,"executeHttpRequest","window.vowOS.service.executeHttpRequest"),
        inspectFunction(service,"getIdentifier","window.vowOS.service.getIdentifier")
      ];
      const supportAppConfig={available:typeof window.Hisense_SupportAppConfig==="function",called:false,status:"NOT_CALLED",value:null,error:null};
      if(supportAppConfig.available){
        try{supportAppConfig.called=true;supportAppConfig.value=compact(window.Hisense_SupportAppConfig());supportAppConfig.status="RETURNED";}
        catch(e){supportAppConfig.called=true;supportAppConfig.status="ERROR";supportAppConfig.error=err(e);}
      }
      const concreteReferences=[],seen={};
      targets.forEach(t=>(t.references||[]).forEach(v=>{const k=String(v).toLowerCase();if(!seen[k]){seen[k]=true;concreteReferences.push({source:t.path,value:v});}}));
      const loadedScripts=await loadedScriptSourceTrace(),runtimeIdentitySurface=runtimeIdentitySurfaceTrace(),runtimeObjectInventory=runtimeObjectInventoryTrace(),globalPhoenixWrappers=globalPhoenixWrapperTrace(),globalIdentityUsage=globalIdentityUsageTrace();
      state.report.permissionSourceTrace={timestamp:new Date().toISOString(),readOnly:true,targets:targets,supportAppConfig:supportAppConfig,concreteReferences:concreteReferences.slice(0,150),loadedScripts:loadedScripts,runtimeIdentitySurface:runtimeIdentitySurface,runtimeObjectInventory:runtimeObjectInventory,globalPhoenixWrappers:globalPhoenixWrappers,globalIdentityUsage:globalIdentityUsage,notes:["Function source/descriptor inspection plus read-only source inspection of already-loaded scripts and runtime bridge objects.","Only same-origin external scripts and inline script text are inspected; cross-origin scripts are skipped.","Sidee's own /app.js is listed but source scanning is skipped to avoid self-generated keyword noise.","Runtime getters, setters, init methods and discovered functions are never invoked.","The complete runtime inventory is unfiltered for vowOSContext, vowOS.service and omi_platform; descriptor access does not evaluate accessor values.","Global Phoenix wrapper scan searches existing function source for vowOS.service.execute, phoenix://service/ and register patterns without invoking anything.","Global identity-usage scan searches existing function source for vowOSContext.init/getAppIdentifier/getAppId and navigator.appIdentifier without invoking anything.","Install-pipeline helpers are inspected but never invoked.","Hisense_SupportAppConfig is the only diagnostic function invoked; no install/uninstall, fileWrite, setters or guessed HiUtils APIs are called."]};
      const ctxProps=runtimeObjectInventory.objects.vowOSContext.propertyCount,svcProps=runtimeObjectInventory.objects.vowOSService.propertyCount,omiProps=runtimeObjectInventory.objects.omiPlatform.propertyCount;
      set("permissionSourceTraceState","Trace complete · identity wrappers "+globalIdentityUsage.matches.length+" · init refs "+globalIdentityUsage.patternCounts["vowOSContext.init"]+" · Phoenix wrappers "+globalPhoenixWrappers.matches.length+".");
      log("Permission source trace complete",{available:targets.filter(t=>t.available).map(t=>t.path),references:concreteReferences.slice(0,20),identityUsageSummary:{scannedFunctions:globalIdentityUsage.scannedFunctionCount,matches:globalIdentityUsage.matches.length,patternCounts:globalIdentityUsage.patternCounts},phoenixSummary:{scannedFunctions:globalPhoenixWrappers.scannedFunctionCount,matches:globalPhoenixWrappers.matches.length,paths:globalPhoenixWrappers.uniquePhoenixPaths},runtimeInventorySummary:{contextProperties:ctxProps,serviceProperties:svcProps,omiProperties:omiProps,omiAvailable:runtimeObjectInventory.objects.omiPlatform.available},runtimeIdentitySummary:{navigatorAppIdentifier:runtimeIdentitySurface.exact.navigatorAppIdentifier},scriptSummary:{count:loadedScripts.scriptCount,inspected:loadedScripts.inspectedCount,matched:loadedScripts.matchedScriptCount,mapAppInfoFieldsFound:loadedScripts.mapAppInfoFieldsFound},supportAppConfig:supportAppConfig});
      await save("permission-source-trace");
    }catch(e){set("permissionSourceTraceState","Trace failed: "+err(e));log("Permission source trace failed",err(e));}
    finally{state.running=false;}
  }

  function target(){ return {app_id:$("appId").value.trim(),app_name:$("appName").value.trim(),app_url:$("appUrl").value.trim(),icon_url:$("iconUrl").value.trim(),store_type:state.config&&state.config.nuvio&&state.config.nuvio.store_type||"store"}; }
  function icon(t){ if(t.icon_url)return t.icon_url; try{return new URL("/assets/images/icon.png",t.app_url).toString();}catch(e){return "";} }
  function v2(t){const i=icon(t);return {Id:t.app_id,appId:t.app_id,AppName:t.app_name,name:t.app_name,Title:t.app_name,URL:t.app_url,url:t.app_url,StartCommand:t.app_url,Thumb:i,Icon_96:i,Image:i,IconURL:i,icon:i,StoreType:t.store_type||"store",storeType:t.store_type||"store",PreInstall:false,isShowOnLauncher:true};}
  async function installCall(method){
    const t=target(),isV2=method==="v2",fn=isV2?window.Hisense_installApp_V2:window.Hisense_installApp,rec={timestamp:new Date().toISOString(),method:method,identifierSnapshot:capture("installTest"),payload:null,returnValue:null,externalCallback:null,error:null};
    if(typeof fn!=="function"){rec.error="Install API unavailable";return rec;}
    let resolveCb;const cbp=new Promise(r=>resolveCb=r),cb=s=>{rec.externalCallback=compact(s);resolveCb(s);};
    const tr=await traced("install-"+method,async()=>{try{if(isV2){const p=v2(t);rec.payload=compact(p);rec.returnValue=compact(fn(p,cb));}else{const i=icon(t);rec.payload={appId:t.app_id,appName:t.app_name,icon:i,url:t.app_url,storeType:t.store_type||"store"};rec.returnValue=compact(fn(t.app_id,t.app_name,i,i,i,t.app_url,t.store_type||"store",cb));}try{await withTimeout(cbp,4000,"install callback");}catch(e){}return rec.returnValue;}catch(e){rec.error=err(e);throw e;}});
    rec.trace=tr.trace;if(tr.error&&!rec.error)rec.error=tr.error;return rec;
  }
  function parseJson(v){if(typeof v!=="string")return null;const s=v.trim();if(!s||"[{".indexOf(s[0])<0)return null;try{return JSON.parse(s);}catch(e){return null;}}
  function collect(v,out,d){if(d>3||out.length>=80||v==null)return;const p=parseJson(v);if(p)return collect(p,out,d+1);if(Array.isArray(v)){v.slice(0,50).forEach(x=>collect(x,out,d+1));return;}if(typeof v!=="object")return;out.push(v);Object.keys(v).slice(0,30).forEach(k=>{try{const c=v[k],j=parseJson(c);if(j)collect(j,out,d+1);else if(c&&typeof c==="object")collect(c,out,d+1);}catch(e){}});}
  function matches(r,t){const needles=[t.app_id,t.app_name,t.app_url].filter(Boolean).map(x=>String(x).toLowerCase());const vals=[];try{Object.keys(r).slice(0,30).forEach(k=>{const v=r[k];if(typeof v==="string"||typeof v==="number")vals.push(String(v).toLowerCase());});}catch(e){}return needles.some(n=>vals.some(v=>v.indexOf(n)>=0));}
  async function installed(){if(typeof window.Hisense_getInstalledApps!=="function")return {available:false,match:false,count:0};let resolveCb;const cbp=new Promise(r=>resolveCb=r);let ret;try{ret=window.Hisense_getInstalledApps(function(){resolveCb(Array.prototype.slice.call(arguments));});}catch(e){return {available:true,match:false,count:0,error:err(e)};}let cb=null;try{cb=await withTimeout(cbp,1200,"installed apps callback");}catch(e){cb=null;}const raw=[];collectAppRecords(ret,raw,0,[]);collectAppRecords(cb,raw,0,[]);const records=prepareRecords(raw),t=target();return {available:true,match:records.some(x=>matches(x.raw,t)),count:records.length};}
  function appInfo(){if(typeof window.HiUtils_createRequest!=="function")return {available:false,match:false,count:0};try{const rawResult=window.HiUtils_createRequest("fileRead",{path:"websdk/Appinfo.json",mode:6}),raw=[],t=target();collectAppRecords(rawResult,raw,0,[]);const records=prepareRecords(raw);return {available:true,ok:!!(rawResult&&rawResult.ret),match:records.some(x=>matches(x.raw,t)),count:records.length};}catch(e){return {available:true,match:false,count:0,error:err(e)};}}

  const APP_FIELD_ALIASES={
    id:["id"],appId:["appId","appid"],name:["name","appName"],title:["title"],url:["url"],startCommand:["startCommand"],
    storeType:["storeType"],openMode:["openMode"],venderId:["venderId"],vendorId:["vendorId"],unifiedAppName:["unifiedAppName"],
    initialFrom:["initialFrom"],configUrl:["configUrl"],configUrlDownload:["configUrlDownload"],appBundle:["appBundle"],
    package:["package"],packageName:["packageName"],version:["version"],developer:["developer"],categoryName:["categoryName"],
    subCategory:["subCategory"],preInstall:["preInstall"],isShowOnLauncher:["isShowOnLauncher"]
  };
  const APP_INTERESTING_RE=/(permission|privilege|security|appconfig|config|identifier|client|role|customer|origin|domain|package|bundle|store|install|launch|sign|certificate|auth)/i;
  const APP_PERMISSION_RE=/(permission|privilege|security|appconfig|identifier|client|role|customer|sign|certificate|auth)/i;
  const APP_CONFIG_RE=/(appconfig|config)/i;
  const APP_REFERENCE_RE=/(\.json(?:$|[?#])|\/config\/|\/appconfig|websdk\/|file:\/\/|\/data\/|\/home\/|package|manifest)/i;
  const APP_SKIP_RE=/(image|icon|thumb|screenshot|poster|background|wallpaper|promotional|description|base64|blob)/i;

  function scalar(v){
    if(v===undefined||v===null)return v;
    if(typeof v==="string")return cut(v,500);
    if(typeof v==="number"||typeof v==="boolean")return v;
    return null;
  }
  function field(obj,aliases){
    if(!obj||typeof obj!=="object")return null;
    let keys=[];try{keys=Object.keys(obj);}catch(e){return null;}
    const map={};keys.forEach(k=>{const l=String(k).toLowerCase();if(!Object.prototype.hasOwnProperty.call(map,l))map[l]=k;});
    for(let i=0;i<aliases.length;i++){
      const real=map[String(aliases[i]).toLowerCase()];
      if(real===undefined)continue;
      let v;try{v=obj[real];}catch(e){continue;}
      const safe=scalar(v);
      if(safe!==null&&safe!==undefined)return safe;
    }
    return null;
  }
  function normalizeApp(obj){
    const out={};
    Object.keys(APP_FIELD_ALIASES).forEach(k=>{const v=field(obj,APP_FIELD_ALIASES[k]);if(v!==null&&v!==undefined)out[k]=v;});
    return out;
  }
  function appLike(obj){
    if(!obj||typeof obj!=="object"||Array.isArray(obj))return false;
    let keys=[];try{keys=Object.keys(obj).map(k=>String(k).toLowerCase());}catch(e){return false;}
    return ["id","appid","unifiedappname","name","appname","title","url","startcommand"].some(k=>keys.indexOf(k)>=0);
  }
  function collectAppRecords(v,out,d,seen){
    d=d||0;seen=seen||[];
    if(d>3||out.length>=120||v==null)return;
    const parsed=parseJson(v);if(parsed)return collectAppRecords(parsed,out,d,seen);
    if(typeof v!=="object")return;
    if(seen.indexOf(v)>=0)return;seen.push(v);
    if(Array.isArray(v)){v.slice(0,100).forEach(x=>collectAppRecords(x,out,d+1,seen));seen.pop();return;}
    if(appLike(v))out.push(v);
    let keys=[];try{keys=Object.keys(v).slice(0,60);}catch(e){}
    keys.forEach(k=>{
      if(APP_SKIP_RE.test(k))return;
      let child;try{child=v[k];}catch(e){return;}
      const parsedChild=parseJson(child);
      if(child&&typeof child==="object")collectAppRecords(child,out,d+1,seen);
      else if(parsedChild)collectAppRecords(parsedChild,out,d+1,seen);
    });
    seen.pop();
  }
  function recordKey(n){
    const ids=[n.id,n.appId,n.unifiedAppName].filter(meaningful).map(v=>String(v).trim().toLowerCase());
    if(ids.length)return "id:"+ids.join("|");
    const urls=[n.url,n.startCommand].filter(meaningful).map(v=>String(v).trim().toLowerCase());
    if(urls.length)return "url:"+urls.join("|");
    const names=[n.name,n.title].filter(meaningful).map(v=>String(v).trim().toLowerCase());
    return names.length?"name:"+names.join("|"):JSON.stringify(n);
  }
  function prepareRecords(records){
    const out=[],seen={};
    records.forEach(raw=>{const norm=normalizeApp(raw),key=recordKey(norm);if(!key||seen[key])return;seen[key]=true;out.push({raw:raw,norm:norm});});
    return out;
  }
  function tokenSet(n,keys){
    const out=[];keys.forEach(k=>{if(meaningful(n[k]))out.push(String(n[k]).trim().toLowerCase());});return out;
  }
  function overlaps(a,b){return a.some(v=>b.indexOf(v)>=0);}
  function matchRecord(a,b){
    const ai=tokenSet(a,["id","appId","unifiedAppName"]),bi=tokenSet(b,["id","appId","unifiedAppName"]);if(ai.length&&bi.length&&overlaps(ai,bi))return 3;
    const au=tokenSet(a,["url","startCommand"]),bu=tokenSet(b,["url","startCommand"]);if(au.length&&bu.length&&overlaps(au,bu))return 2;
    const an=tokenSet(a,["name","title"]),bn=tokenSet(b,["name","title"]);if(an.length&&bn.length&&overlaps(an,bn))return 1;
    return 0;
  }
  function sourceFields(prepared){
    const seen={};prepared.forEach(x=>{let keys=[];try{keys=Object.keys(x.raw);}catch(e){}keys.slice(0,80).forEach(k=>{if(!APP_SKIP_RE.test(k))seen[k]=true;});});
    return Object.keys(seen).sort().slice(0,100);
  }
  function firstValue(a,b,key){return meaningful(a&&a[key])?a[key]:meaningful(b&&b[key])?b[key]:null;}
  function classify(inst,info){
    const store=firstValue(info,inst,"storeType"),pre=firstValue(info,inst,"preInstall");
    if(pre===true||String(pre).toLowerCase()==="true"||String(store).toLowerCase()==="preinstalled"||String(store).toLowerCase()==="preinstall")return {type:"preinstalled",evidence:{storeType:store,preInstall:pre}};
    if(String(store).toLowerCase()==="store")return {type:"store",evidence:{storeType:store,preInstall:pre}};
    if(String(store).toLowerCase()==="hisense")return {type:"hisense",evidence:{storeType:store,preInstall:pre}};
    return {type:"unknown",evidence:{storeType:store,preInstall:pre}};
  }
  function identityFor(inst,info){
    const out={};["id","appId","unifiedAppName","name","title","url","startCommand"].forEach(k=>{const v=firstValue(info,inst,k);if(v!==null)out[k]=v;});return out;
  }
  function scanMetadata(raw,prefix,collector){
    function walk(v,path,d){
      if(d>3||collector.count>=40||v==null)return;
      if(typeof v==="string"){
        if(APP_REFERENCE_RE.test(v)&&!/^(data:|blob:)/i.test(v)){
          const id=collector.appId||"unknown",key=id+"|"+prefix+"."+path+"|"+v;
          if(!collector.referenceSeen[key]&&collector.references.length<80){collector.referenceSeen[key]=true;collector.references.push({appId:id,field:prefix+"."+path,value:cut(v,500),reason:"json/config/path-like"});}
        }
        return;
      }
      if(typeof v!=="object")return;
      if(collector.seen.indexOf(v)>=0)return;collector.seen.push(v);
      if(Array.isArray(v)){v.slice(0,30).forEach((x,i)=>walk(x,path+"["+i+"]",d+1));collector.seen.pop();return;}
      let keys=[];try{keys=Object.keys(v).slice(0,60);}catch(e){}
      keys.forEach(k=>{
        if(collector.count>=40||APP_SKIP_RE.test(k))return;
        let child;try{child=v[k];}catch(e){return;}
        const next=path?path+"."+k:k,safe=scalar(child);
        if(APP_INTERESTING_RE.test(k)){
          collector.fields[k]=true;
          if(safe!==null&&safe!==undefined){collector.metadata[prefix+"."+next]=safe;collector.count++;}
        }
        if(typeof child==="string")walk(child,next,d+1);
        else if(child&&typeof child==="object")walk(child,next,d+1);
      });
      collector.seen.pop();
    }
    walk(raw,"",0);
  }
  function makeAppRecord(instEntry,infoEntry,references,referenceSeen){
    const inst=instEntry?instEntry.norm:{},info=infoEntry?infoEntry.norm:{},identity=identityFor(inst,info);
    const collector={appId:String(identity.appId||identity.id||identity.unifiedAppName||identity.name||"unknown"),metadata:{},fields:{},count:0,references:references,referenceSeen:referenceSeen,seen:[]};
    if(instEntry)scanMetadata(instEntry.raw,"installedApps",collector);
    if(infoEntry)scanMetadata(infoEntry.raw,"appInfo",collector);
    return {identity:identity,installedApps:instEntry?inst:{},appInfo:infoEntry?info:{},matchedSources:[instEntry?"Hisense_getInstalledApps":null,infoEntry?"websdk/Appinfo.json":null].filter(Boolean),interestingMetadata:collector.metadata,classification:classify(inst,info),_fields:Object.keys(collector.fields)};
  }
  function distribution(apps){
    const out={},special=["storeType","openMode","venderId","vendorId","unifiedAppName","initialFrom","configUrl","configUrlDownload","appBundle","package","packageName","version","developer","categoryName","subCategory","preInstall","isShowOnLauncher"];
    function add(k,v){if(v===null||v===undefined||typeof v==="object")return;if(!out[k])out[k]={};const s=String(v)===""?"(empty)":cut(v,120);out[k][s]=(out[k][s]||0)+1;}
    apps.forEach(a=>{
      const counted={};
      special.forEach(k=>{const v=firstValue(a.appInfo,a.installedApps,k);if(v!==null&&v!==undefined){add(k,v);counted[k.toLowerCase()]=true;}});
      const perField={};Object.keys(a.interestingMetadata).forEach(path=>{const k=path.split(".").pop();if(!Object.prototype.hasOwnProperty.call(perField,k))perField[k]=a.interestingMetadata[path];});
      Object.keys(perField).slice(0,40).forEach(k=>{const key=k.toLowerCase();if(counted[key])return;add(k,perField[k]);counted[key]=true;});
    });
    return out;
  }
  function countTypes(apps){const out={store:0,hisense:0,preinstalled:0,unknown:0};apps.forEach(a=>{const k=a.classification&&a.classification.type||"unknown";out[k]=(out[k]||0)+1;});return out;}
  function formatCounts(o){return Object.keys(o).filter(k=>o[k]>0).map(k=>k+" "+o[k]).join(" · ")||"—";}
  async function installedMetadataSource(){
    if(typeof window.Hisense_getInstalledApps!=="function")return {source:{available:false,status:"UNAVAILABLE",count:0,fields:[]},records:[]};
    let resolveCb,callbackStatus="WAITING",ret=null,error=null,cb=null;const cbp=new Promise(r=>resolveCb=r);
    try{ret=window.Hisense_getInstalledApps(function(){callbackStatus="RETURNED";resolveCb(Array.prototype.slice.call(arguments));});}catch(e){error=err(e);}
    if(!error){try{cb=await withTimeout(cbp,1500,"installed apps callback");}catch(e){callbackStatus="TIMEOUT";}}
    const raw=[];collectAppRecords(ret,raw,0,[]);collectAppRecords(cb,raw,0,[]);const records=prepareRecords(raw);
    return {source:{available:true,status:error?"ERROR":"RETURNED",callbackStatus:callbackStatus,count:records.length,fields:sourceFields(records),error:error},records:records};
  }
  async function appInfoMetadataSource(){
    if(typeof window.HiUtils_createRequest!=="function")return {source:{available:false,status:"UNAVAILABLE",path:"websdk/Appinfo.json",count:0,fields:[]},records:[],deepDump:[]};
    const r=await traced("installed-app-metadata-appinfo",()=>window.HiUtils_createRequest("fileRead",{path:"websdk/Appinfo.json",mode:6}));
    const raw=[];collectAppRecords(r.value,raw,0,[]);const records=prepareRecords(raw),tr=r.trace&&r.trace.result||{};
    // Keep the original AppInfo record objects as returned by the already-known read-only fileRead.
    // No field filtering/normalization/truncation is applied here: nested appInfo/showInfo and empty values stay intact.
    const deepDump=records.map(x=>x.raw);
    return {source:{available:true,status:r.error?"ERROR":"RETURNED",path:"websdk/Appinfo.json",count:records.length,fields:sourceFields(records),ret:tr.ret,code:tr.code,msg:tr.msg,error:r.error||null},records:records,deepDump:deepDump};
  }
  async function inspectInstalledMetadata(){
    if(state.running)return;state.running=true;set("metadataState","Inspecting read-only installed app metadata…");
    try{
      const a=await installedMetadataSource(),b=await appInfoMetadataSource(),used=[],apps=[],references=[],referenceSeen={};
      a.records.forEach(inst=>{let best=-1,bestScore=0;for(let i=0;i<b.records.length;i++){if(used[i])continue;const score=matchRecord(inst.norm,b.records[i].norm);if(score>bestScore){bestScore=score;best=i;if(score===3)break;}}if(best>=0){used[best]=true;apps.push(makeAppRecord(inst,b.records[best],references,referenceSeen));}else apps.push(makeAppRecord(inst,null,references,referenceSeen));});
      b.records.forEach((info,i)=>{if(!used[i])apps.push(makeAppRecord(null,info,references,referenceSeen));});
      const fields={};apps.forEach(x=>{x._fields.forEach(k=>fields[k]=true);delete x._fields;});
      const special=["storeType","openMode","venderId","vendorId","unifiedAppName","initialFrom","configUrl","configUrlDownload","appBundle","package","packageName","version","developer","categoryName","subCategory","preInstall","isShowOnLauncher"];
      special.forEach(k=>{if(apps.some(x=>meaningful(firstValue(x.appInfo,x.installedApps,k))))fields[k]=true;});
      const fieldNames=Object.keys(fields).sort(),seenFieldNames={},interestingFields=fieldNames.filter(k=>{const key=k.toLowerCase();if(seenFieldNames[key])return false;seenFieldNames[key]=true;return true;}),summary={installedAppsCount:a.source.count,appInfoCount:b.source.count,matchedCount:apps.filter(x=>x.matchedSources.length===2).length,appsCount:apps.length,storeTypes:countTypes(apps),interestingFieldsSeen:interestingFields,permissionLikeFieldsSeen:interestingFields.filter(k=>APP_PERMISSION_RE.test(k)),configLikeFieldsSeen:interestingFields.filter(k=>APP_CONFIG_RE.test(k))};
      summary.appInfoDeepDumpCount=b.deepDump.length;
      const result={timestamp:new Date().toISOString(),sources:{installedApps:a.source,appInfo:b.source},apps:apps,appInfoDeepDump:{path:"websdk/Appinfo.json",readOnly:true,recordCount:b.deepDump.length,records:b.deepDump},fieldDistribution:distribution(apps),discoveredReferences:references,summary:summary};
      state.report.installedAppMetadata=result;
      set("metadataApps",summary.installedAppsCount);set("metadataMatched",summary.matchedCount);set("metadataStoreTypes",formatCounts(summary.storeTypes));set("metadataFields",interestingFields.length?interestingFields.slice(0,8).join(", ")+(interestingFields.length>8?" +"+(interestingFields.length-8):""):"none");set("metadataReferences",references.length);
      set("metadataState","Inspection complete. Full AppInfo deep dump saved read-only ("+b.deepDump.length+" records).");log("Installed app metadata inspected",{installedApps:summary.installedAppsCount,appInfo:summary.appInfoCount,matched:summary.matchedCount,deepDump:b.deepDump.length,references:references.length});await save("installed-app-metadata");
    }catch(e){set("metadataState","Inspection failed: "+err(e));log("Installed app metadata inspection failed",err(e));}
    finally{state.running=false;}
  }

  async function verify(){const a=await installed(),b=appInfo(),r={timestamp:new Date().toISOString(),installedApps:a,appInfo:b,verified:!!(a.match||b.match)};state.report.verification=r;set("verifyOutput",r.verified?"VERIFIED INSTALLED":"NOT INSTALLED");return r;}
  function gate(test,verification,previous){const i=test&&test.trace&&test.trace.result||{},code=i.code,ret=i.ret,msg=String(i.msg||"");if(verification&&verification.verified)return "PASSED";if(Number(code)===503&&/permission|appconfig/i.test(msg))return "REJECTED";if(ret===true)return "PASSED";if(test&&test.returnValue===false)return "REJECTED";if(previous&&previous.internal&&(previous.internal.code!==code||previous.internal.ret!==ret||String(previous.internal.msg||"")!==msg))return "CHANGED";return "UNKNOWN";}
  async function installTest(method){
    if(state.running)return;const t=target();if(!t.app_id||!t.app_name||!t.app_url)return set("installState","App ID, name and URL are required.");state.running=true;set("installState","Running explicit install permission test…");const prev=state.report.installTest,chosen=method||(typeof window.Hisense_installApp_V2==="function"?"v2":"legacy"),test=await installCall(chosen),verification=await verify(),internal=test.trace&&test.trace.result||{ret:null,code:null,msg:null},status=gate(test,verification,prev);
    state.report.installTest={timestamp:test.timestamp,method:chosen,identifierUsed:test.trace?test.trace.identifier:null,appIdentifier:test.identifierSnapshot.appIdentifier,appId:test.identifierSnapshot.appId,roleId:test.identifierSnapshot.roleId,customerId:test.identifierSnapshot.customerId,payload:test.payload,returnValue:test.returnValue,internal:internal,externalCallback:test.externalCallback,error:test.error,verification:verification};state.report.summary.permissionGate=status;renderSummary();set("installState",status+" · internal ret "+String(internal.ret)+" · code "+String(internal.code)+" · callback "+String(test.externalCallback)+" · "+(verification.verified?"verified installed":"not installed"));log("Install permission test",state.report.installTest);state.running=false;await save("install-permission-test");
  }
  async function tempIdentifier(){
    const value=$("temporaryIdentifier").value.trim();if(!value)return set("temporaryIdentifierState","Enter an identifier first. No test was run.");let svc=null;try{svc=window.vowOS&&window.vowOS.service;}catch(e){}if(!svc||typeof svc.getIdentifier!=="function")return set("temporaryIdentifierState","vowOS.service.getIdentifier is unavailable.");const original=svc.getIdentifier;let r=null;
    try{svc.getIdentifier=function(){return value;};r=await traced("temporary-identifier-readonly",()=>{if(typeof window.HiUtils_createRequest!=="function")throw new Error("HiUtils_createRequest unavailable");return window.HiUtils_createRequest("fileRead",{path:"websdk/Appinfo.json",mode:6});});set("temporaryIdentifierState","Test complete · identifier "+value+" · code "+String(r.trace.result&&r.trace.result.code));log("Temporary Identifier Test complete and restored",r.trace);}catch(e){set("temporaryIdentifierState","Test error: "+err(e));}finally{try{svc.getIdentifier=original;}catch(e){}}state.report.temporaryIdentifierTest={timestamp:new Date().toISOString(),identifier:value,trace:r&&r.trace?r.trace:null};await save("temporary-identifier-test");
  }


  const APPINFO_PATH="websdk/Appinfo.json";
  const APPINFO_MODE=6;
  const DIRECT_WRITE_ARTICLE="https://pikabu.ru/story/jellyfin_na_vidaa_9_13617347";
  const DIRECT_WRITE_REFERENCE="weinzii/vidaa-edge@94c3134911cbd4b813eea1f88c56819c0981518b";

  async function hashText(text){
    const value=String(text);
    try{
      if(window.crypto&&window.crypto.subtle&&typeof TextEncoder!=="undefined"){
        const digest=await window.crypto.subtle.digest("SHA-256",new TextEncoder().encode(value));
        return {algorithm:"SHA-256",value:Array.prototype.map.call(new Uint8Array(digest),b=>b.toString(16).padStart(2,"0")).join("")};
      }
    }catch(e){}
    let h=2166136261;
    for(let i=0;i<value.length;i++){h^=value.charCodeAt(i);h=Math.imul(h,16777619)>>>0;}
    return {algorithm:"FNV1A-32-FALLBACK",value:h.toString(16).padStart(8,"0")};
  }
  function stableValue(v){
    if(Array.isArray(v))return v.map(stableValue);
    if(v&&typeof v==="object"){
      const out={};
      Object.keys(v).sort().forEach(k=>{out[k]=stableValue(v[k]);});
      return out;
    }
    return v;
  }
  function stableJson(v){try{return JSON.stringify(stableValue(v));}catch(e){return null;}}
  function parseRegistryRaw(raw){
    const out={valid:false,parsed:null,error:null,appInfoCount:null};
    if(typeof raw!=="string"){out.error="fileRead did not return a string msg";return out;}
    try{
      const parsed=JSON.parse(raw);
      if(!parsed||typeof parsed!=="object"||Array.isArray(parsed)||!Array.isArray(parsed.AppInfo))throw new Error("Expected object with AppInfo array");
      out.valid=true;out.parsed=parsed;out.appInfoCount=parsed.AppInfo.length;
    }catch(e){out.error=err(e);}
    return out;
  }
  function registryDiff(before,after){
    if(!before||!after)return {structurallyEqual:false,changedTopLevelKeys:["unavailable"],appInfoChangedIndices:[]};
    const keys={},changed=[],indices=[];
    Object.keys(before).forEach(k=>keys[k]=true);Object.keys(after).forEach(k=>keys[k]=true);
    Object.keys(keys).sort().forEach(k=>{if(stableJson(before[k])!==stableJson(after[k]))changed.push(k);});
    const a=Array.isArray(before.AppInfo)?before.AppInfo:[],b=Array.isArray(after.AppInfo)?after.AppInfo:[],n=Math.max(a.length,b.length);
    for(let i=0;i<n&&indices.length<40;i++)if(stableJson(a[i])!==stableJson(b[i]))indices.push(i);
    return {structurallyEqual:stableJson(before)===stableJson(after),changedTopLevelKeys:changed,appInfoChangedIndices:indices,beforeCount:a.length,afterCount:b.length};
  }
  async function readAppInfoRegistry(source){
    if(typeof window.HiUtils_createRequest!=="function")return {ok:false,error:"HiUtils_createRequest unavailable",raw:null,parsed:null,parseValid:false,hash:null,length:null,appInfoCount:null,response:null,trace:null};
    const r=await traced(source||"direct-appinfo-read",()=>window.HiUtils_createRequest("fileRead",{path:APPINFO_PATH,mode:APPINFO_MODE}));
    const response=r&&r.value,raw=response&&response.ret===true&&typeof response.msg==="string"?response.msg:null,parsed=parseRegistryRaw(raw),hash=raw!==null?await hashText(raw):null;
    return {ok:!!(response&&response.ret===true&&raw!==null&&parsed.valid),error:r&&r.error||parsed.error||null,raw:raw,parsed:parsed.parsed,parseValid:parsed.valid,hash:hash,length:raw!==null?raw.length:null,appInfoCount:parsed.appInfoCount,response:labSafe(response),trace:r&&r.trace||null};
  }

  async function refreshDirectBuildMatch(){
    const response=await fetch("/api/status?cb="+Date.now(),{cache:"no-store"}),data=await response.json();
    if(!response.ok||!data.ok)throw new Error("Could not verify Sidee server build");
    state.report.serverBuildId=data.clientBuildId||null;
    state.report.buildMatch=!!data.clientBuildId&&data.clientBuildId===CLIENT_BUILD_ID;
    if(!state.report.buildMatch)throw new Error("Client/server build mismatch; reload Sidee before any AppInfo write");
    return data.clientBuildId;
  }
  async function createAppInfoBackup(raw,hash){
    const clientSha256=hash&&hash.algorithm==="SHA-256"?hash.value:null;
    const response=await fetch("/api/appinfo/backup",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({sessionId:state.report.sessionId,raw:raw,clientSha256:clientSha256,clientBuildId:CLIENT_BUILD_ID})});
    const data=await response.json();
    if(!response.ok||!data.ok)throw new Error(data.error||"Could not create AppInfo backup");
    if(clientSha256&&data.backup.sha256!==clientSha256)throw new Error("Backup hash mismatch");
    return data.backup;
  }
  async function loadAppInfoBackup(backup){
    if(!backup||!backup.backupId)throw new Error("No Sidee AppInfo backup is selected");
    const url="/api/appinfo/backup?sessionId="+encodeURIComponent(state.report.sessionId)+"&backupId="+encodeURIComponent(backup.backupId);
    const response=await fetch(url,{cache:"no-store"}),data=await response.json();
    if(!response.ok||!data.ok)throw new Error(data.error||"Could not load AppInfo backup");
    if(data.backup.sessionId!==state.report.sessionId||data.backup.backupId!==backup.backupId)throw new Error("Backup identity mismatch");
    if(backup.sha256&&data.backup.sha256!==backup.sha256)throw new Error("Backup SHA-256 mismatch");
    return data.backup;
  }
  async function fileWriteAppInfo(raw,source){
    const request={path:APPINFO_PATH,mode:APPINFO_MODE,writedata:raw};
    if(typeof window.HiUtils_createRequest!=="function")return {request:request,response:null,result:{ret:null,code:null,msg:null},error:"HiUtils_createRequest unavailable"};
    const r=await traced(source||"direct-appinfo-write",()=>window.HiUtils_createRequest("fileWrite",request));
    return {request:request,response:labSafe(r&&r.value),result:r&&r.trace&&r.trace.result||traceResult(r&&r.value),error:r&&r.error||null};
  }
  function writeRet(write){
    const raw=write&&write.response;
    if(raw===true||raw===false)return raw;
    if(raw&&typeof raw==="object"&&Object.prototype.hasOwnProperty.call(raw,"ret"))return raw.ret;
    const ret=write&&write.result&&write.result.ret;
    return ret===true||ret===false?ret:null;
  }
  function directCandidateEntry(){
    const t=target(),i=icon(t),day=new Date().toISOString().split("T")[0];
    return {Id:t.app_id,AppName:t.app_name,Title:t.app_name,URL:t.app_url,StartCommand:t.app_url,IconURL:i,Icon_96:i,Image:i,Thumb:i,Type:"Browser",InstallTime:day,RunTimes:0,StoreType:"custom",PreInstall:false};
  }
  function directEntryBasis(){
    return {
      strategy:"Minimal known-working direct-write shape shared by the Pikabu Jellyfin guide and vidaa-edge new method; not claimed to be the theoretical minimum.",
      sourceArticle:DIRECT_WRITE_ARTICLE,
      sourceImplementation:DIRECT_WRITE_REFERENCE,
      included:["Id","AppName","Title","URL","StartCommand","IconURL","Icon_96","Image","Thumb","Type=Browser","InstallTime","RunTimes=0","StoreType=custom","PreInstall=false"],
      existingTvObservations:{
        Smartone:{StoreType:"store",openMode:98,venderId:9999},
        Stremio:{StoreType:"hisense",openMode:99,venderId:9999},
        Duplecast:{StoreType:"store",openMode:98,venderId:9999,packaged:0}
      },
      omitted:["openMode","venderId","packaged","configUrl","configUrlDownload","mediaId"],
      omissionReason:"The direct-write sources do not require these fields and observed values vary across installed apps; adding them would be speculative."
    };
  }
  function renderDirectAppInfoWriteLab(r){
    set("directWriteOriginalHash",r&&r.original&&r.original.rawHash?r.original.rawHash.value:"—");
    set("directWriteOriginalCount",r&&r.original?r.original.appInfoCount:"—");
    set("directWriteBackup",r&&r.backup?r.backup.backupId:"—");
    set("directWriteResponse",r&&r.response?("ret "+String(r.response.result&&r.response.result.ret)+" · code "+String(r.response.result&&r.response.result.code)):"—");
    set("directWriteReadbackHash",r&&r.readback&&r.readback.rawHash?r.readback.rawHash.value:"—");
    set("directWriteCapability",r&&r.writeCapability?r.writeCapability:"NOT_RUN");
    set("directAppInfoWriteState",r?(r.writeCapability+" · "+(r.identicalBeforeAfter===true?"readback identical":r.identicalBeforeAfter===false?"readback changed":"no verified readback")):"Not run yet.");
    const add=$("addNuvioDirectBtn"),restore=$("restoreAppInfoBackupBtn");
    if(add)add.disabled=!(r&&r.writeCapability==="WRITE_ALLOWED_AND_IDENTICAL");
    if(restore)restore.disabled=!(r&&r.backup&&r.backup.backupId);
    state.report.summary.appInfoWrite=r&&r.writeCapability||"NOT_RUN";
    renderSummary();
  }
  async function directAppInfoWriteLab(options){
    if(state.running)return null;
    state.running=true;set("directAppInfoWriteState","Preparing backup-protected AppInfo no-op write…");
    let report={timestamp:new Date().toISOString(),clientBuildId:CLIENT_BUILD_ID,serverBuildId:state.report.serverBuildId,buildMatch:state.report.buildMatch,pageContext:pageContext(),accessMode:accessMode(),serverAccess:state.report.serverAccess,sourceArticle:{url:DIRECT_WRITE_ARTICLE,claim:"Third-party report describes direct Appinfo fileWrite on VIDAA 9."},sourceImplementation:{ref:DIRECT_WRITE_REFERENCE,call:"HiUtils_createRequest('fileWrite', {path:'websdk/Appinfo.json', mode:6, writedata:...})"},original:null,backup:null,writeApi:"HiUtils_createRequest('fileWrite', ...)",request:null,response:null,readback:null,structuralDiff:null,identicalBeforeAfter:null,writeCapability:"INCONCLUSIVE",candidateEntry:{entry:directCandidateEntry(),basis:directEntryBasis()},addResult:null,restoreResult:null,conclusion:null,remote:!!(options&&options.remote)};
    try{
      report.serverBuildId=await refreshDirectBuildMatch();report.buildMatch=true;
      const before=await readAppInfoRegistry("direct-appinfo-noop-before");
      report.original={raw:before.raw,parsed:before.parsed,rawHash:before.hash,length:before.length,appInfoCount:before.appInfoCount,parseValid:before.parseValid,readResponse:before.response,error:before.error};
      if(!before.ok||!before.parseValid)throw new Error(before.error||"Could not obtain valid Appinfo JSON");
      report.backup=await createAppInfoBackup(before.raw,before.hash);
      if(before.hash&&before.hash.algorithm==="SHA-256"&&report.backup.sha256!==before.hash.value)throw new Error("Server backup does not match the exact Appinfo content");
      const write=await fileWriteAppInfo(before.raw,"direct-appinfo-noop-filewrite");
      report.request=write.request;report.response={raw:write.response,result:write.result,error:write.error};
      const after=await readAppInfoRegistry("direct-appinfo-noop-readback");
      report.readback={raw:after.raw,parsed:after.parsed,rawHash:after.hash,length:after.length,appInfoCount:after.appInfoCount,parseValid:after.parseValid,readResponse:after.response,error:after.error};
      if(after.parseValid&&after.parsed){
        report.structuralDiff=registryDiff(before.parsed,after.parsed);
        report.identicalBeforeAfter=!!(before.hash&&after.hash&&before.hash.algorithm===after.hash.algorithm&&before.hash.value===after.hash.value&&before.length===after.length&&before.appInfoCount===after.appInfoCount&&report.structuralDiff.structurallyEqual);
      }
      const ret=writeRet(write);
      if(after.parseValid&&report.identicalBeforeAfter===false)report.writeCapability="WRITE_CHANGED_CONTENT";
      else if(ret===false)report.writeCapability="WRITE_DENIED";
      else if(!after.ok||!after.parseValid)report.writeCapability="READBACK_FAILED";
      else if(ret===true&&report.identicalBeforeAfter===true)report.writeCapability="WRITE_ALLOWED_AND_IDENTICAL";
      else report.writeCapability="INCONCLUSIVE";
      report.conclusion=report.writeCapability;
    }catch(e){
      report.error=err(e);
      report.conclusion=report.writeCapability||"INCONCLUSIVE";
    }finally{
      state.report.directAppInfoWriteLab=report;renderDirectAppInfoWriteLab(report);log("Direct AppInfo write lab",{capability:report.writeCapability,backup:report.backup&&report.backup.backupId,error:report.error||null});state.running=false;await save("direct-appinfo-write-lab");
    }
    return report;
  }
  async function inspectHspdkContext(){
    if(state.running)return;
    state.running=true;
    try{
      const report=window.SideeHspdkContext();
      state.report.legacyHspdkContext=report;
      set("hspdkContextState",report.status+" · "+report.sourceMatches.length+" source references · no native calls");
      await save("legacy-hspdk-context");
    }catch(e){set("hspdkContextState","Context inspection failed: "+err(e));}
    finally{state.running=false;}
  }
  $("hspdkContextBtn").addEventListener("click",inspectHspdkContext);

  function hspdkHosts(){
    const names=["Hisense","HiBrowser"],out=[];
    for(let i=0;i<names.length;i++){
      try{
        const value=window[names[i]];
        if(value&&(typeof value==="object"||typeof value==="function"))out.push({name:names[i],value:value});
      }catch(e){}
    }
    return out;
  }
  function hspdkHost(preferredName){
    const hosts=hspdkHosts();
    if(preferredName){
      hosts.sort((a,b)=>(a.name===preferredName?-1:0)-(b.name===preferredName?-1:0));
    }
    for(let i=0;i<hosts.length;i++){
      const file=hspdkFile(hosts[i].value);
      if(file&&typeof file.read==="function"&&typeof file.write==="function")return hosts[i];
    }
    for(let i=0;i<hosts.length;i++){
      try{if(typeof hosts[i].value.loadLibrary==="function")return hosts[i];}catch(e){}
    }
    return hosts[0]||{name:null,value:null};
  }
  function hspdkResolveWriter(preferredName){
    const hosts=hspdkHosts();
    if(preferredName){
      hosts.sort((a,b)=>(a.name===preferredName?-1:0)-(b.name===preferredName?-1:0));
    }
    const attempts=[];
    for(let i=0;i<hosts.length;i++){
      const host=hosts[i],attempt={owner:host.name,direct:false,loadAttempted:false,loadReturnValue:null,loadError:null,ready:false};
      let file=hspdkFile(host.value);
      if(file&&typeof file.read==="function"&&typeof file.write==="function"){
        attempt.direct=true;attempt.ready=true;attempts.push(attempt);
        return {name:host.name,value:host.value,file:file,attempts:attempts};
      }
      let loader=null;try{loader=host.value.loadLibrary;}catch(e){}
      if(typeof loader==="function"){
        attempt.loadAttempted=true;
        try{attempt.loadReturnValue=labSafe(loader.call(host.value,"libhspdk-jsx.so"));}catch(e){attempt.loadError=err(e);}
        file=hspdkFile(host.value);
        attempt.ready=!!(file&&typeof file.read==="function"&&typeof file.write==="function");
        attempts.push(attempt);
        if(attempt.ready)return {name:host.name,value:host.value,file:file,attempts:attempts};
      }else attempts.push(attempt);
    }
    return {name:null,value:null,file:null,attempts:attempts};
  }
  function hspdkFnMeta(owner,name){
    if(!owner)return {available:false};
    try{
      const fn=owner[name];
      return {available:typeof fn==="function",descriptor:descriptor(owner,name),name:typeof fn==="function"?(fn.name||name):null,length:typeof fn==="function"?fn.length:null,source:typeof fn==="function"?functionSource(fn):null};
    }catch(e){return {available:false,error:err(e)};}
  }
  function hspdkSnapshot(){
    const hosts=hspdkHosts(),surfaces=hosts.map(entry=>{
      const owner=entry.value;let file=null,fileError=null;
      try{file=owner.File||null;}catch(e){fileError=err(e);}
      return {
        owner:entry.name,
        ownerType:typeof owner,
        loadLibrary:hspdkFnMeta(owner,"loadLibrary"),
        fileAvailable:!!file,
        fileError:fileError,
        fileProperties:file?(()=>{try{return Object.getOwnPropertyNames(file).slice(0,80);}catch(e){return [];}})():[],
        read:hspdkFnMeta(file,"read"),
        write:hspdkFnMeta(file,"write")
      };
    }),selected=hspdkHost(),surface=surfaces.find(x=>x.owner===selected.name)||null;
    return {
      owner:selected.name,
      ownerAvailable:!!selected.value,
      ownerType:surface?surface.ownerType:"missing",
      loadLibrary:surface?surface.loadLibrary:{available:false},
      fileAvailable:surface?surface.fileAvailable:false,
      fileError:surface?surface.fileError:null,
      fileProperties:surface?surface.fileProperties:[],
      read:surface?surface.read:{available:false},
      write:surface?surface.write:{available:false},
      surfaces:surfaces
    };
  }
  function hspdkFile(owner){
    if(!owner)return null;
    try{return owner.File||null;}catch(e){return null;}
  }
  async function hspdkReadRegistry(file,path){
    const out={path:path,ok:false,raw:null,parsed:null,parseValid:false,hash:null,length:null,appInfoCount:null,error:null};
    if(!file||typeof file.read!=="function"){out.error="Legacy File.read unavailable";return out;}
    try{
      const raw=file.read(path,1);
      if(typeof raw!=="string"){out.error="File.read did not return a string";return out;}
      const parsed=parseRegistryRaw(raw);
      out.raw=raw;out.parsed=parsed.parsed;out.parseValid=parsed.valid;out.hash=await hashText(raw);out.length=raw.length;out.appInfoCount=parsed.appInfoCount;out.ok=parsed.valid;out.error=parsed.error||null;
    }catch(e){out.error=err(e);}
    return out;
  }
  async function hspdkFindRegistry(file){
    const paths=["launcher/Appinfo.json","websdk/Appinfo.json"],attempts=[];
    for(let i=0;i<paths.length;i++){
      const r=await hspdkReadRegistry(file,paths[i]);attempts.push({path:r.path,ok:r.ok,error:r.error,length:r.length,appInfoCount:r.appInfoCount});
      if(r.ok)return {registry:r,attempts:attempts};
    }
    return {registry:null,attempts:attempts};
  }
  function hspdkWrite(file,path,raw){
    const out={path:path,mode:1,returnValue:null,error:null,completed:false};
    if(!file||typeof file.write!=="function"){out.error="Legacy File.write unavailable";return out;}
    try{out.returnValue=labSafe(file.write(path,raw,1));out.completed=true;}catch(e){out.error=err(e);}
    return out;
  }
  function hspdkCandidateEntry(parsed){
    const apps=parsed&&Array.isArray(parsed.AppInfo)?parsed.AppInfo:[],useAppId=apps.some(a=>a&&typeof a==="object"&&Object.prototype.hasOwnProperty.call(a,"AppId"))&&!apps.some(a=>a&&typeof a==="object"&&Object.prototype.hasOwnProperty.call(a,"Id"));
    const t=target(),i=icon(t),day=new Date().toISOString().split("T")[0];
    const entry={Thumb:i,Icon_96:i,Image:i,URL:t.app_url,AppName:t.app_name,Title:t.app_name,IconURL:i,StartCommand:t.app_url,InstallTime:day,RunTimes:0,StoreType:"custom",PreInstall:false};
    entry[useAppId?"AppId":"Id"]=t.app_id;
    return entry;
  }
  function hspdkDuplicate(apps,candidate){
    const norm=v=>String(v==null?"":v).trim().toLowerCase(),cid=norm(candidate.Id||candidate.AppId),curl=norm(candidate.URL),cname=norm(candidate.AppName);
    for(let i=0;i<apps.length;i++){
      const a=apps[i]||{};
      if((cid&&norm(a.Id||a.AppId)===cid)||(curl&&norm(a.URL||a.StartCommand)===curl)||(cname&&(norm(a.AppName)===cname||norm(a.Title)===cname)))return {index:i,entry:labSafe(a)};
    }
    return null;
  }
  function hspdkRefreshLauncher(appId){
    const out={available:false,attempted:false,returnValue:null,error:null};
    try{
      const omi=window.omi_platform;
      if(!omi||typeof omi.sendPlatformMessage!=="function")return out;
      out.available=true;out.attempted=true;
      const msg={type:"APPMessage",MsgType:"appControl",action:"updateAppState",source:"browser",startAppType:2,param:{event:"AllAppsUpdate",SubModuleName:"AllApps",startFrom:"",appInfo:appId}};
      out.returnValue=labSafe(omi.sendPlatformMessage(JSON.stringify(msg)));
    }catch(e){out.error=err(e);}
    return out;
  }
  function renderLegacyHspdkLab(r){
    set("legacyHspdkOwner",r&&r.selectedOwner?r.selectedOwner:r&&r.afterLoad&&r.afterLoad.owner?r.afterLoad.owner:r&&r.beforeLoad&&r.beforeLoad.owner?r.beforeLoad.owner:"NONE");
    set("legacyHspdkLibrary",r&&r.libraryLoad?(r.libraryLoad.attempted?(r.libraryLoad.error?"ERROR":"CALLED"):"NOT_NEEDED"):"NOT_RUN");
    set("legacyHspdkPath",r&&r.registry?r.registry.path:"—");
    set("legacyHspdkProbe",r&&r.probe?r.probe.status:"NOT_RUN");
    set("legacyHspdkRestore",r&&r.restore?r.restore.status:"NOT_RUN");
    set("legacyHspdkCapability",r&&r.writeCapability?r.writeCapability:"NOT_RUN");
    set("legacyHspdkState",r?(r.writeCapability+(r.error?" · "+r.error:"")):"Not run yet.");
    const add=$("addNuvioHspdkBtn"),restore=$("restoreHspdkBackupBtn");
    if(add)add.disabled=!(r&&r.writeCapability==="WRITE_ALLOWED_AND_RESTORED");
    if(restore)restore.disabled=!(r&&r.backup&&r.backup.backupId&&r.registry&&r.registry.path);
    if(r&&r.writeCapability)state.report.summary.appInfoWrite="HSPDK_"+r.writeCapability;
    renderSummary();
  }
  async function legacyHspdkWriteLab(){
    if(state.running)return null;
    state.running=true;set("legacyHspdkState","Probing legacy Hisense/HSPDK file writer…");
    const report={timestamp:new Date().toISOString(),pageContext:pageContext(),source:{article:"https://4pda.to/forum/index.php?showtopic=1004810&st=5220",legacyImplementation:"Hisense.File.read/write('launcher/Appinfo.json', mode 1) + libhspdk-jsx.so fallback"},beforeLoad:null,libraryLoad:{attempted:false,library:"libhspdk-jsx.so",returnValue:null,error:null},resolutionAttempts:[],selectedOwner:null,afterLoad:null,registry:null,readAttempts:[],backup:null,probe:null,restore:null,writeCapability:"INCONCLUSIVE",error:null};
    try{
      await refreshDirectBuildMatch();
      report.beforeLoad=hspdkSnapshot();
      const resolved=hspdkResolveWriter();
      report.resolutionAttempts=resolved.attempts;report.selectedOwner=resolved.name;
      const chosenAttempt=resolved.attempts.find(x=>x.owner===resolved.name)||resolved.attempts[resolved.attempts.length-1]||null;
      if(chosenAttempt){
        report.libraryLoad={attempted:!!chosenAttempt.loadAttempted,library:"libhspdk-jsx.so",returnValue:chosenAttempt.loadReturnValue,error:chosenAttempt.loadError||null};
      }
      report.afterLoad=hspdkSnapshot();
      const file=resolved.file;
      if(!file){
        report.writeCapability="WRITER_UNAVAILABLE";
        state.report.legacyHspdkContext=window.SideeHspdkContext();
        throw new Error("Neither Hisense nor HiBrowser exposed a usable legacy File.read/File.write surface");
      }
      const found=await hspdkFindRegistry(file);report.readAttempts=found.attempts;
      if(!found.registry)throw new Error("No valid AppInfo registry readable through the legacy File API");
      const before=found.registry;report.registry={path:before.path,hash:before.hash,length:before.length,appInfoCount:before.appInfoCount};
      report.backup=await createAppInfoBackup(before.raw,before.hash);
      const probeRaw=before.raw.endsWith("\n")?before.raw+" ":before.raw+"\n",probeParsed=parseRegistryRaw(probeRaw);
      if(!probeParsed.valid||stableJson(probeParsed.parsed)!==stableJson(before.parsed))throw new Error("Could not construct structurally identical whitespace probe");
      const probeHash=await hashText(probeRaw),write=hspdkWrite(file,before.path,probeRaw),probeRead=await hspdkReadRegistry(file,before.path);
      const probeApplied=!!(write.completed&&probeRead.ok&&probeRead.raw===probeRaw&&probeRead.hash&&probeHash&&probeRead.hash.algorithm===probeHash.algorithm&&probeRead.hash.value===probeHash.value&&stableJson(probeRead.parsed)===stableJson(before.parsed));
      report.probe={status:probeApplied?"PROBE_APPLIED":"PROBE_NOT_APPLIED",write:write,expectedHash:probeHash,readbackHash:probeRead.hash,readbackLength:probeRead.length,structurallyIdentical:probeRead.parseValid?stableJson(probeRead.parsed)===stableJson(before.parsed):false,error:probeRead.error||write.error||null};
      const restoreWrite=hspdkWrite(file,before.path,before.raw),restored=await hspdkReadRegistry(file,before.path);
      const restoredExact=!!(restoreWrite.completed&&restored.ok&&restored.raw===before.raw&&restored.hash&&before.hash&&restored.hash.algorithm===before.hash.algorithm&&restored.hash.value===before.hash.value);
      report.restore={status:restoredExact?"RESTORED_IDENTICAL":"RESTORE_NOT_VERIFIED",write:restoreWrite,readbackHash:restored.hash,readbackLength:restored.length,error:restored.error||restoreWrite.error||null};
      if(probeApplied&&restoredExact)report.writeCapability="WRITE_ALLOWED_AND_RESTORED";
      else if(probeApplied&&!restoredExact)report.writeCapability="RESTORE_FAILED";
      else if(write.error)report.writeCapability="WRITE_ERROR";
      else report.writeCapability="WRITE_NOT_APPLIED";
    }catch(e){report.error=err(e);}
    finally{
      state.report.legacyHspdkWriteLab=report;renderLegacyHspdkLab(report);log("Legacy HSPDK write lab",{owner:report.afterLoad&&report.afterLoad.owner,path:report.registry&&report.registry.path,capability:report.writeCapability,error:report.error});state.running=false;await save("legacy-hspdk-write-lab");
    }
    return report;
  }
  async function restoreHspdkBackup(){
    const lab=state.report.legacyHspdkWriteLab;
    if(!lab||!lab.backup||!lab.registry||!lab.registry.path)return set("legacyHspdkRestoreState","No HSPDK backup from this session is available.");
    if(state.running)return;state.running=true;set("legacyHspdkRestoreState","Restoring exact HSPDK AppInfo backup…");
    let result={timestamp:new Date().toISOString(),status:"INCONCLUSIVE",error:null};
    try{
      await refreshDirectBuildMatch();
      const resolved=hspdkResolveWriter(lab.selectedOwner||null),file=resolved.file;
      result.resolutionAttempts=resolved.attempts;result.selectedOwner=resolved.name;
      if(!file)throw new Error("Legacy File API unavailable on both Hisense and HiBrowser surfaces");
      const backup=await loadAppInfoBackup(lab.backup),write=hspdkWrite(file,lab.registry.path,backup.raw),after=await hspdkReadRegistry(file,lab.registry.path),hash=await hashText(backup.raw);
      result.write=write;result.readbackHash=after.hash;result.status=write.completed&&after.ok&&after.raw===backup.raw&&after.hash&&hash&&after.hash.value===hash.value?"RESTORED_IDENTICAL":"RESTORE_NOT_VERIFIED";
    }catch(e){result.error=err(e);}
    finally{lab.manualRestore=result;state.report.legacyHspdkWriteLab=lab;set("legacyHspdkRestoreState",result.status+(result.error?" · "+result.error:""));state.running=false;await save("legacy-hspdk-restore");}
  }
  async function addNuvioHspdk(){
    const lab=state.report.legacyHspdkWriteLab;
    if(!lab||lab.writeCapability!=="WRITE_ALLOWED_AND_RESTORED")return set("legacyHspdkAddState","Run a successful HSPDK write+restore proof first.");
    if(state.running)return;state.running=true;set("legacyHspdkAddState","Adding Nuvio through the verified legacy File writer…");
    let result={timestamp:new Date().toISOString(),status:"INCONCLUSIVE",backup:null,candidate:null,refresh:null,error:null};
    try{
      await refreshDirectBuildMatch();
      const resolved=hspdkResolveWriter(lab.selectedOwner||null),file=resolved.file;
      result.resolutionAttempts=resolved.attempts;result.selectedOwner=resolved.name;
      if(!file)throw new Error("Legacy File API unavailable on both Hisense and HiBrowser surfaces");
      const before=await hspdkReadRegistry(file,lab.registry.path);if(!before.ok)throw new Error(before.error||"Could not read current legacy AppInfo");
      result.backup=await createAppInfoBackup(before.raw,before.hash);
      const candidate=hspdkCandidateEntry(before.parsed);result.candidate=candidate;
      const duplicate=hspdkDuplicate(before.parsed.AppInfo,candidate);
      if(duplicate){result.status="APPINFO_ENTRY_PRESENT";result.duplicate=duplicate;}
      else{
        const next=JSON.parse(before.raw);next.AppInfo.push(candidate);const raw=JSON.stringify(next),write=hspdkWrite(file,lab.registry.path,raw),after=await hspdkReadRegistry(file,lab.registry.path);
        result.write=write;result.readback={hash:after.hash,length:after.length,appInfoCount:after.appInfoCount,error:after.error};
        const found=after.ok?hspdkDuplicate(after.parsed.AppInfo,candidate):null;
        const preserved=!!(after.ok&&after.parsed.AppInfo.length===before.parsed.AppInfo.length+1&&before.parsed.AppInfo.every((entry,i)=>stableJson(entry)===stableJson(after.parsed.AppInfo[i])));
        if(write.completed&&found&&preserved){result.status="APPINFO_ENTRY_PRESENT";result.found=found;result.refresh=hspdkRefreshLauncher(candidate.Id||candidate.AppId);}
        else{
          const backup=await loadAppInfoBackup(result.backup),restoreWrite=hspdkWrite(file,lab.registry.path,backup.raw),restored=await hspdkReadRegistry(file,lab.registry.path);
          result.emergencyRestore={write:restoreWrite,status:restoreWrite.completed&&restored.ok&&restored.raw===backup.raw?"RESTORED_IDENTICAL":"RESTORE_NOT_VERIFIED"};
          throw new Error("Nuvio write was not verified; original registry restore attempted");
        }
      }
    }catch(e){result.error=err(e);}
    finally{lab.addResult=result;state.report.legacyHspdkWriteLab=lab;set("legacyHspdkAddState",result.status+(result.error?" · "+result.error:"")+(result.status==="APPINFO_ENTRY_PRESENT"?" · launcher refresh sent when available":""));log("HSPDK Nuvio add",result);state.running=false;await save("legacy-hspdk-add-nuvio");}
  }

  function directDuplicate(apps,candidate){
    const norm=v=>String(v==null?"":v).trim().toLowerCase();
    for(let i=0;i<apps.length;i++){
      const a=apps[i]||{};
      if(norm(a.Id)===norm(candidate.Id)||norm(a.URL)===norm(candidate.URL)||norm(a.AppName)===norm(candidate.AppName)||norm(a.Title)===norm(candidate.Title))return {index:i,entry:labSafe(a)};
    }
    return null;
  }
  async function addNuvioDirect(){
    const lab=state.report.directAppInfoWriteLab;
    if(!lab||lab.writeCapability!=="WRITE_ALLOWED_AND_IDENTICAL")return set("directAddState","Run a successful identical no-op write first.");
    if(state.running)return;state.running=true;set("directAddState","Reading current AppInfo and creating a fresh backup…");
    let result={timestamp:new Date().toISOString(),status:"INCONCLUSIVE",fileWriteStatus:"NOT_RUN",entryStatus:"NOT_PRESENT",launcherStatus:"UNKNOWN_REBOOT_REQUIRED",launchStatus:"NOT_TESTED",backup:null,candidateEntry:directCandidateEntry(),error:null};
    try{
      await refreshDirectBuildMatch();
      const before=await readAppInfoRegistry("direct-add-before");
      if(!before.ok||!before.parseValid)throw new Error(before.error||"Current Appinfo is not valid");
      result.before={rawHash:before.hash,length:before.length,appInfoCount:before.appInfoCount};
      result.backup=await createAppInfoBackup(before.raw,before.hash);
      const duplicate=directDuplicate(before.parsed.AppInfo,result.candidateEntry);
      if(duplicate){
        result.status="APPINFO_ENTRY_PRESENT";result.entryStatus="APPINFO_ENTRY_PRESENT";result.duplicate=duplicate;result.note="No write performed because a matching Id, URL or name already exists.";
      }else{
        const next=JSON.parse(before.raw);next.AppInfo.push(result.candidateEntry);
        const writeRaw=JSON.stringify(next),write=await fileWriteAppInfo(writeRaw,"direct-add-nuvio-filewrite");
        result.request=write.request;result.response={raw:write.response,result:write.result,error:write.error};result.fileWriteStatus=writeRet(write)===true?"FILE_WRITE_SUCCESS":"FILE_WRITE_FAILED";
        const after=await readAppInfoRegistry("direct-add-readback");
        result.readback={raw:after.raw,parsed:after.parsed,rawHash:after.hash,length:after.length,appInfoCount:after.appInfoCount,parseValid:after.parseValid,error:after.error};
        const found=after.parseValid?directDuplicate(after.parsed.AppInfo,result.candidateEntry):null;
        result.entryStatus=found?"APPINFO_ENTRY_PRESENT":"APPINFO_ENTRY_NOT_PRESENT";
        result.existingEntriesPreserved=!!(after.parseValid&&after.parsed.AppInfo.length===before.parsed.AppInfo.length+1&&before.parsed.AppInfo.every((entry,i)=>stableJson(entry)===stableJson(after.parsed.AppInfo[i]))&&stableJson(Object.assign({},before.parsed,{AppInfo:[]}))===stableJson(Object.assign({},after.parsed,{AppInfo:[]})));
        if(found&&result.existingEntriesPreserved){result.status="APPINFO_ENTRY_PRESENT";result.note="Registry readback contains Nuvio and all previous entries are structurally preserved. Launcher visibility still requires observation/reboot.";}
        else if(writeRet(write)===true){result.status="FILE_WRITE_SUCCESS";result.note="fileWrite returned success, but the required AppInfo readback conditions were not fully verified.";}
        else result.status="INCONCLUSIVE";
      }
    }catch(e){result.error=err(e);}
    finally{
      lab.addResult=result;state.report.directAppInfoWriteLab=lab;set("directAddState",result.status+(result.error?" · "+result.error:"")+(result.status==="APPINFO_ENTRY_PRESENT"?" · reboot TV may be required for launcher visibility":""));log("Direct Nuvio AppInfo action",result);state.running=false;await save("direct-appinfo-add-nuvio");
    }
  }
  async function restoreAppInfoBackup(){
    const lab=state.report.directAppInfoWriteLab,originalBackup=lab&&lab.backup;
    if(!originalBackup||!originalBackup.backupId)return set("directRestoreState","No Sidee backup from this session is available.");
    if(state.running)return;state.running=true;set("directRestoreState","Verifying backup and protecting the current registry…");
    let result={timestamp:new Date().toISOString(),backupId:originalBackup.backupId,status:"INCONCLUSIVE",preRestoreBackup:null,error:null};
    try{
      await refreshDirectBuildMatch();
      const currentRegistry=await readAppInfoRegistry("direct-restore-current");
      if(!currentRegistry.ok||!currentRegistry.parseValid)throw new Error(currentRegistry.error||"Current Appinfo is not valid");
      result.preRestoreBackup=await createAppInfoBackup(currentRegistry.raw,currentRegistry.hash);
      const backup=await loadAppInfoBackup(originalBackup),backupHash=await hashText(backup.raw),parsed=parseRegistryRaw(backup.raw);
      if(!parsed.valid)throw new Error("Stored backup JSON is invalid");
      if(backupHash.algorithm==="SHA-256"&&backupHash.value!==backup.sha256)throw new Error("Stored backup hash verification failed");
      result.verifiedBackup={backupId:backup.backupId,sessionId:backup.sessionId,createdAt:backup.createdAt,sha256:backup.sha256,bytes:backup.bytes,appInfoCount:backup.appInfoCount,path:backup.path};
      const write=await fileWriteAppInfo(backup.raw,"direct-restore-filewrite");
      result.request=write.request;result.response={raw:write.response,result:write.result,error:write.error};
      const after=await readAppInfoRegistry("direct-restore-readback"),structural=after.parseValid?registryDiff(parsed.parsed,after.parsed):null;
      result.readback={rawHash:after.hash,length:after.length,appInfoCount:after.appInfoCount,parseValid:after.parseValid,error:after.error};
      result.identicalToBackup=!!(after.parseValid&&after.hash&&backupHash&&after.hash.algorithm===backupHash.algorithm&&after.hash.value===backupHash.value&&structural&&structural.structurallyEqual);
      result.status=result.identicalToBackup?"RESTORED_IDENTICAL":writeRet(write)===false?"RESTORE_WRITE_DENIED":"RESTORE_NOT_VERIFIED";
    }catch(e){result.error=err(e);}
    finally{
      lab.restoreResult=result;state.report.directAppInfoWriteLab=lab;set("directRestoreState",result.status+(result.error?" · "+result.error:""));log("AppInfo backup restore",result);state.running=false;await save("direct-appinfo-restore");
    }
  }

  function labSafe(v,d,seen){
    d=d||0;seen=seen||[];
    if(v===undefined)return "[undefined]";
    if(v===null||typeof v==="boolean"||typeof v==="number")return v;
    if(typeof v==="string")return cut(v,20000);
    if(typeof v==="function")return "[function "+(v.name||"anonymous")+"]";
    if(typeof v!=="object")return cut(v,500);
    if(d>=5)return Array.isArray(v)?"[array depth limit]":"[object depth limit]";
    if(seen.indexOf(v)>=0)return "[circular]";
    seen.push(v);
    const out=Array.isArray(v)?[]:{};
    try{
      const keys=Object.keys(v).slice(0,120);
      keys.forEach(k=>{try{out[k]=labSafe(v[k],d+1,seen);}catch(e){out[k]="[read error: "+err(e)+"]";}});
      if(Array.isArray(v)&&v.length>120)out.push("[truncated "+(v.length-120)+" items]");
    }catch(e){}
    seen.pop();
    return out;
  }
  function labScalar(v){
    if(v===null||v===undefined)return null;
    if(typeof v!=="string"&&typeof v!=="number")return null;
    const s=String(v).trim();
    if(!meaningful(s)||s.length>160||/^(https?:|file:|data:|blob:)/i.test(s))return null;
    return s;
  }
  function addIdentityCandidate(list,map,value,provenance,score,meta){
    const s=labScalar(value);if(!s)return;
    const key=s.toLowerCase();
    if(!map[key]){
      map[key]={value:s,score:score||0,provenance:[],meta:meta||null};
      list.push(map[key]);
    }else if((score||0)>map[key].score)map[key].score=score||0;
    if(provenance&&map[key].provenance.indexOf(provenance)<0)map[key].provenance.push(provenance);
  }
  function targetedRuntimeIdentifierCandidates(add){
    const nameRe=/^(?:app_?identifier|appidentifier|identifier|app_?id|appid|application_?id|client_?id|clientid)$/i;
    const secretRe=/(token|secret|password|cookie|auth|key)/i;
    let names=[];try{names=Object.getOwnPropertyNames(window);}catch(e){return;}
    const scan=(owner,prefix,limit)=>{
      let props=[];try{props=Object.getOwnPropertyNames(owner);}catch(e){return;}
      for(let i=0;i<props.length&&i<limit;i++){
        const name=props[i];if(!nameRe.test(name)||secretRe.test(name))continue;
        let d=null;try{d=Object.getOwnPropertyDescriptor(owner,name);}catch(e){}
        if(!d||!Object.prototype.hasOwnProperty.call(d,"value"))continue;
        const s=labScalar(d.value);if(s)add(s,prefix+"."+name,55,{kind:"runtime-data-descriptor"});
      }
    };
    scan(window,"window",1200);
    for(let i=0;i<names.length&&i<1200;i++){
      let d=null;try{d=Object.getOwnPropertyDescriptor(window,names[i]);}catch(e){}
      if(!d||!Object.prototype.hasOwnProperty.call(d,"value")||!d.value||typeof d.value!=="object")continue;
      const obj=d.value;if(obj===window||obj===document||obj===navigator)continue;
      let child=[];try{child=Object.getOwnPropertyNames(obj);}catch(e){continue;}
      if(child.length>120)continue;
      scan(obj,"window."+names[i],120);
    }
  }
  function addRecordCandidates(prepared,sourceBase,add,baseScore){
    (prepared||[]).slice(0,120).forEach((entry,idx)=>{
      const n=entry&&entry.norm||{},label=String(n.name||n.title||"");
      const bonus=/(vidaa|hisense|store|browser|launcher|system|stremio|smartone|duplecast)/i.test(label)?15:0;
      ["id","appId","unifiedAppName"].forEach(field=>{
        if(meaningful(n[field]))add(n[field],sourceBase+"["+idx+"]."+field,baseScore+bonus,{kind:"installed-app-id",appName:label||null,field:field});
      });
    });
  }
  function responseJson(v){try{return JSON.stringify(v);}catch(e){return String(v);}}
  function labDiff(base,test){
    const br=base.result||{},tr=test.result||{};
    const retChanged=JSON.stringify(br.ret)!==JSON.stringify(tr.ret);
    const codeChanged=JSON.stringify(br.code)!==JSON.stringify(tr.code);
    const msgChanged=String(br.msg||"")!==String(tr.msg||"");
    const responseChanged=base._responseJson!==test._responseJson;
    return {retChanged:retChanged,codeChanged:codeChanged,msgChanged:msgChanged,responseChanged:responseChanged,backendChanged:retChanged||codeChanged||msgChanged||responseChanged};
  }
  async function withTemporaryServiceIdentifier(value,operation){
    let svc=null;try{svc=window.vowOS&&window.vowOS.service;}catch(e){}
    if(!svc||typeof svc.getIdentifier!=="function")throw new Error("vowOS.service.getIdentifier is unavailable");
    const hadOwn=Object.prototype.hasOwnProperty.call(svc,"getIdentifier");
    const ownDescriptor=hadOwn?Object.getOwnPropertyDescriptor(svc,"getIdentifier"):null;
    const originalResolved=svc.getIdentifier;
    let originalIdentifier=null;try{originalIdentifier=compact(originalResolved.call(svc));}catch(e){}
    const replacement=function(){return value;};
    const meta={originalIdentifier:originalIdentifier,identifierTested:value,method:null,applied:false,restored:false,restoredIdentifier:null,error:null};
    try{
      try{svc.getIdentifier=replacement;}catch(e){}
      if(svc.getIdentifier===replacement){meta.method="assignment";meta.applied=true;}
      else{
        try{
          Object.defineProperty(svc,"getIdentifier",{value:replacement,writable:true,configurable:true,enumerable:ownDescriptor?!!ownDescriptor.enumerable:true});
          if(svc.getIdentifier===replacement){meta.method="defineOwnProperty";meta.applied=true;}
        }catch(e){meta.error="override failed: "+err(e);}
      }
      if(!meta.applied)throw new Error(meta.error||"Could not apply temporary identifier override");
      const valueOut=await operation(meta);
      return {value:valueOut,meta:meta};
    }finally{
      try{
        if(hadOwn)Object.defineProperty(svc,"getIdentifier",ownDescriptor);
        else delete svc.getIdentifier;
      }catch(e){meta.error=(meta.error?meta.error+"; ":"")+"restore failed: "+err(e);}
      try{meta.restored=svc.getIdentifier===originalResolved;}catch(e){meta.restored=false;}
      try{meta.restoredIdentifier=compact(svc.getIdentifier());}catch(e){meta.restoredIdentifier=null;}
    }
  }
  async function labReadProbe(identifier,label){
    const request={service:"hiutils",api:"fileRead",args:{path:"websdk/Appinfo.json",mode:6}};
    let result=null,override=null;
    if(identifier===null){
      result=await traced(label||"identity-lab-baseline",()=>{if(typeof window.HiUtils_createRequest!=="function")throw new Error("HiUtils_createRequest unavailable");return window.HiUtils_createRequest("fileRead",request.args);});
    }else{
      const wrapped=await withTemporaryServiceIdentifier(identifier,async()=>{
        return traced(label||"identity-lab-test",()=>{if(typeof window.HiUtils_createRequest!=="function")throw new Error("HiUtils_createRequest unavailable");return window.HiUtils_createRequest("fileRead",request.args);});
      });
      result=wrapped.value;override=wrapped.meta;
    }
    const response=labSafe(result&&result.value),trace=result&&result.trace||{},summary=trace.result||traceResult(result&&result.value);
    return {timestamp:new Date().toISOString(),identifierTested:identifier,override:override,request:request,response:response,responseRef:null,result:summary,error:result&&result.error||null,_rawValue:result&&result.value,_responseJson:responseJson(response)};
  }
  function publicLabProbe(p){
    return {timestamp:p.timestamp,identifierTested:p.identifierTested,override:p.override,request:p.request,response:p.response,responseRef:p.responseRef,result:p.result,error:p.error};
  }
  function renderIdentityLab(r){
    set("identityLabOriginal",r&&meaningful(r.originalIdentifier)?r.originalIdentifier:"EMPTY");
    set("identityLabCandidates",r?r.candidateIdentifiers.length:0);
    set("identityLabTests",r?r.tests.length:0);
    set("identityLabDifferences",r?r.tests.filter(x=>x.responseDiff&&x.responseDiff.backendChanged).length:0);
    set("identityLabConclusion",r?r.conclusionHint:"NOT_RUN");
    set("identityOverrideLabState",r?(r.conclusionHint+" · "+r.tests.length+" read-only override test(s)."):"Not run yet.");
    const input=$("identityPermissionIdentifier");
    if(r&&input&&!input.value&&r.candidateIdentifiers.length)input.value=r.candidateIdentifiers[0].value;
  }
  async function identityOverrideLab(){
    if(state.running)return;
    state.running=true;set("identityOverrideLabState","Running controlled read-only identity tests…");
    try{
      let svc=null;try{svc=window.vowOS&&window.vowOS.service;}catch(e){}
      const original=svc&&typeof svc.getIdentifier==="function"?call(svc,"getIdentifier"):{status:"UNAVAILABLE",value:null};
      const baselineProbe=await labReadProbe(null,"identity-lab-baseline");
      const candidates=[],candidateMap={};
      const add=(value,provenance,score,meta)=>addIdentityCandidate(candidates,candidateMap,value,provenance,score,meta);
      const snap=current()||capture("identityLabDiscovery");
      [["serviceIdentifier",snap&&snap.serviceIdentifier],["appIdentifier",snap&&snap.appIdentifier],["appId",snap&&snap.appId],["navigatorAppIdentifier",snap&&snap.navigatorAppIdentifier]].forEach(pair=>{const x=pair[1];if(x&&x.status==="RETURNED")add(x.value,"runtime."+pair[0],100,{kind:"runtime-identity"});});
      try{
        const raw=[];collectAppRecords(baselineProbe._rawValue,raw,0,[]);
        addRecordCandidates(prepareRecords(raw),"websdk/Appinfo.json",add,80);
      }catch(e){}
      try{
        const installedSource=await installedMetadataSource();
        addRecordCandidates(installedSource.records,"Hisense_getInstalledApps",add,65);
      }catch(e){}
      targetedRuntimeIdentifierCandidates(add);
      candidates.sort((a,b)=>b.score-a.score||a.value.localeCompare(b.value));
      const listed=candidates.slice(0,40).map(c=>({value:c.value,score:c.score,provenance:c.provenance,meta:c.meta}));
      const selected=candidates.slice(0,8),tests=[];
      for(let i=0;i<selected.length;i++){
        const candidate=selected[i];
        let probe;
        try{probe=await labReadProbe(candidate.value,"identity-lab-candidate");}
        catch(e){probe={timestamp:new Date().toISOString(),identifierTested:candidate.value,override:{applied:false,restored:false,error:err(e)},request:{service:"hiutils",api:"fileRead",args:{path:"websdk/Appinfo.json",mode:6}},response:null,responseRef:null,result:{ret:null,code:null,msg:null},error:err(e),_responseJson:""};}
        const difference=labDiff(baselineProbe,probe);
        if(!difference.responseChanged){probe.response=null;probe.responseRef="identityOverrideLab.baselineProbe.response";}
        tests.push({candidate:{value:candidate.value,score:candidate.score,provenance:candidate.provenance,meta:candidate.meta},probe:publicLabProbe(probe),responseDiff:difference});
      }
      let conclusion="INCONCLUSIVE",note="Read-only fileRead behavior did not prove how installApplication validates AppConfig.";
      if(!listed.length){conclusion="NO_REAL_IDENTIFIER_AVAILABLE";note="No concrete non-empty identifier candidate was available from the targeted runtime and installed-app sources.";}
      else if(tests.some(x=>x.responseDiff.backendChanged)){conclusion="IDENTIFIER_AFFECTS_BACKEND";note="At least one concrete identifier changed the read-only local-service response. This does not by itself prove install permission.";}
      else if(tests.length){note="Concrete identifiers were accepted by the temporary client wrapper, but the harmless fileRead response stayed equivalent to baseline. The install permission gate remains untested by this lab.";}
      const report={timestamp:new Date().toISOString(),clientBuildId:CLIENT_BUILD_ID,serverBuildId:state.report.serverBuildId,buildMatch:state.report.buildMatch,originalIdentifier:original&&original.value,candidateIdentifiers:listed,baselineProbe:publicLabProbe(baselineProbe),tests:tests,backendDifferenceCount:tests.filter(x=>x.responseDiff.backendChanged).length,restored:tests.every(x=>x.probe&&x.probe.override&&x.probe.override.restored!==false),conclusionHint:conclusion,conclusionNote:note,permissionProbe:{status:"NOT_RUN",reason:"No known harmless request has been shown to hit the installApplication AppConfig permission gate. Use the separate explicit candidate permission test only if you accept that a permitted request may install the target app."}};
      state.report.identityOverrideLab=report;renderIdentityLab(report);log("Identity Override Lab complete",{candidates:listed.length,tested:tests.length,differences:report.backendDifferenceCount,conclusion:conclusion});await save("identity-override-lab");
    }catch(e){
      const report={timestamp:new Date().toISOString(),candidateIdentifiers:[],tests:[],restored:false,conclusionHint:"INCONCLUSIVE",error:err(e)};
      state.report.identityOverrideLab=report;renderIdentityLab(report);set("identityOverrideLabState","Lab failed: "+err(e));log("Identity Override Lab failed",err(e));await save("identity-override-lab-error");
    }finally{state.running=false;}
  }

  function writeGateResult(write){
    const r=write&&write.result||{};
    return {ret:r.ret===undefined?null:r.ret,code:r.code===undefined?null:r.code,msg:r.msg===undefined?null:String(r.msg),error:write&&write.error||null};
  }
  function writeGateDiff(base,test){
    const a=base||{},b=test||{};
    return {
      retChanged:JSON.stringify(a.ret)!==JSON.stringify(b.ret),
      codeChanged:JSON.stringify(a.code)!==JSON.stringify(b.code),
      msgChanged:String(a.msg||"")!==String(b.msg||""),
      errorChanged:String(a.error||"")!==String(b.error||""),
      backendChanged:JSON.stringify(a.ret)!==JSON.stringify(b.ret)||JSON.stringify(a.code)!==JSON.stringify(b.code)||String(a.msg||"")!==String(b.msg||"")||String(a.error||"")!==String(b.error||"")
    };
  }
  function identityRegistryReadback(before,after){
    const diff=before&&before.parsed&&after&&after.parsed?registryDiff(before.parsed,after.parsed):null;
    const identical=!!(before&&after&&before.raw!==null&&after.raw!==null&&before.raw===after.raw&&before.length===after.length&&before.appInfoCount===after.appInfoCount&&diff&&diff.structurallyEqual);
    return {ok:!!(after&&after.ok&&after.parseValid),identical:identical,rawHash:after&&after.hash||null,length:after&&after.length||null,appInfoCount:after&&after.appInfoCount||null,parseValid:!!(after&&after.parseValid),structuralDiff:diff,error:after&&after.error||null};
  }
  function renderIdentityWriteGateLab(r){
    set("identityLabOriginal",r&&meaningful(r.originalIdentifier)?r.originalIdentifier:"EMPTY");
    set("identityLabCandidates",r&&r.candidateIdentifiers?r.candidateIdentifiers.length:0);
    set("identityLabTests",r&&r.tests?r.tests.length:0);
    set("identityLabDifferences",r&&r.tests?r.tests.filter(x=>x.responseDiff&&x.responseDiff.backendChanged).length:0);
    set("identityLabConclusion",r&&r.conclusionHint?r.conclusionHint:"NOT_RUN");
    set("identityOverrideLabState",r?(r.conclusionHint+" · "+(r.tests?r.tests.length:0)+" write-gate candidate test(s)."):"Not run yet.");
  }
  async function identityWriteGateLab(options){
    if(state.running)return null;
    state.running=true;set("identityOverrideLabState","Preparing backup-protected identifier write-gate test…");
    const report={
      timestamp:new Date().toISOString(),
      clientBuildId:CLIENT_BUILD_ID,
      serverBuildId:state.report.serverBuildId,
      buildMatch:state.report.buildMatch,
      pageContext:pageContext(),
      accessMode:accessMode(),
      originalIdentifier:null,
      backup:null,
      baselineWrite:null,
      candidateIdentifiers:[],
      tests:[],
      maxCandidateWrites:6,
      stoppedEarly:false,
      stopReason:null,
      restored:true,
      registryUnchanged:true,
      conclusionHint:"INCONCLUSIVE",
      conclusionNote:null,
      remote:!!(options&&options.remote),
      safety:"Every write uses the exact raw Appinfo string read before the lab. Nuvio is never added. Identifier overrides are restored in finally."
    };
    try{
      report.serverBuildId=await refreshDirectBuildMatch();report.buildMatch=true;
      let svc=null;try{svc=window.vowOS&&window.vowOS.service;}catch(e){}
      const original=svc&&typeof svc.getIdentifier==="function"?call(svc,"getIdentifier"):{status:"UNAVAILABLE",value:null};
      report.originalIdentifier=original&&original.value;

      const before=await readAppInfoRegistry("identity-write-gate-read-before");
      if(!before.ok||!before.parseValid)throw new Error(before.error||"Could not obtain valid Appinfo JSON");
      report.registryBefore={rawHash:before.hash,length:before.length,appInfoCount:before.appInfoCount,parseValid:before.parseValid};
      report.backup=await createAppInfoBackup(before.raw,before.hash);
      if(before.hash&&before.hash.algorithm==="SHA-256"&&report.backup.sha256!==before.hash.value)throw new Error("Server backup does not match the exact Appinfo content");

      const baselineWrite=await fileWriteAppInfo(before.raw,"identity-write-gate-baseline");
      const baselineAfter=await readAppInfoRegistry("identity-write-gate-baseline-readback");
      const baselineReadback=identityRegistryReadback(before,baselineAfter);
      report.baselineWrite={identifier:report.originalIdentifier,result:writeGateResult(baselineWrite),request:{path:APPINFO_PATH,mode:APPINFO_MODE,writedata:"[exact registry raw; omitted from report summary]"},readback:baselineReadback};
      if(!baselineReadback.identical){
        report.registryUnchanged=false;report.stoppedEarly=true;report.stopReason="BASELINE_REGISTRY_CHANGED";report.conclusionHint="REGISTRY_CHANGED_ABORTED";report.conclusionNote="The baseline no-op write did not read back identically. Candidate writes were not attempted.";
        throw new Error("Baseline no-op write changed or invalidated Appinfo; candidate writes aborted");
      }

      const baselineGate=report.baselineWrite.result;
      if(baselineGate.ret===true){
        report.stoppedEarly=true;report.stopReason="BASELINE_WRITE_ALREADY_ALLOWED";report.conclusionHint="BASELINE_WRITE_ALLOWED";report.conclusionNote="The original identifier already passed the no-op write gate, so spoofing candidates would add no useful evidence.";
      }else{
        const candidates=[],candidateMap={};
        const add=(value,provenance,score,meta)=>addIdentityCandidate(candidates,candidateMap,value,provenance,score,meta);
        const snap=current()||capture("identityWriteGateDiscovery");
        [["serviceIdentifier",snap&&snap.serviceIdentifier],["appIdentifier",snap&&snap.appIdentifier],["appId",snap&&snap.appId],["navigatorAppIdentifier",snap&&snap.navigatorAppIdentifier]].forEach(pair=>{const x=pair[1];if(x&&x.status==="RETURNED")add(x.value,"runtime."+pair[0],120,{kind:"runtime-identity"});});
        (before.parsed.AppInfo||[]).slice(0,120).forEach((entry,idx)=>{
          const label=String(entry&&entry.AppName||entry&&entry.Title||"");
          const bonus=/(vidaa|hisense|store|browser|launcher|system|stremio|smartone|duplecast)/i.test(label)?20:0;
          [["Id",entry&&entry.Id],["appId",entry&&entry.appId],["unifiedAppName",entry&&entry.unifiedAppName]].forEach(pair=>{if(meaningful(pair[1]))add(pair[1],"websdk/Appinfo.json["+idx+"]."+pair[0],90+bonus,{kind:"appinfo-id",appName:label||null,field:pair[0]});});
        });
        try{
          const installedSource=await installedMetadataSource();
          addRecordCandidates(installedSource.records,"Hisense_getInstalledApps",add,70);
        }catch(e){}
        targetedRuntimeIdentifierCandidates(add);
        candidates.sort((a,b)=>b.score-a.score||a.value.localeCompare(b.value));
        report.candidateIdentifiers=candidates.slice(0,40).map(c=>({value:c.value,score:c.score,provenance:c.provenance,meta:c.meta}));

        const selected=candidates.slice(0,report.maxCandidateWrites);
        for(let i=0;i<selected.length;i++){
          const candidate=selected[i];
          await refreshDirectBuildMatch();
          let wrapped=null,testRecord={candidate:{value:candidate.value,score:candidate.score,provenance:candidate.provenance,meta:candidate.meta},write:null,readback:null,override:null,responseDiff:null,contentChanged:false,error:null};
          try{
            wrapped=await withTemporaryServiceIdentifier(candidate.value,async()=>{
              const write=await fileWriteAppInfo(before.raw,"identity-write-gate-candidate");
              const after=await readAppInfoRegistry("identity-write-gate-candidate-readback");
              return {write:write,after:after};
            });
            testRecord.override=wrapped.meta;
            const gate=writeGateResult(wrapped.value.write),readback=identityRegistryReadback(before,wrapped.value.after);
            testRecord.write={result:gate,request:{path:APPINFO_PATH,mode:APPINFO_MODE,writedata:"[exact registry raw; omitted from report summary]"}};
            testRecord.readback=readback;
            testRecord.contentChanged=!readback.identical;
            testRecord.responseDiff=writeGateDiff(baselineGate,gate);
            if(!wrapped.meta.restored)report.restored=false;
            if(testRecord.contentChanged){
              report.registryUnchanged=false;report.stoppedEarly=true;report.stopReason="CANDIDATE_REGISTRY_CHANGED";report.tests.push(testRecord);break;
            }
            report.tests.push(testRecord);
            if(testRecord.responseDiff.backendChanged){
              report.stoppedEarly=true;report.stopReason="WRITE_GATE_RESPONSE_CHANGED";break;
            }
          }catch(e){
            testRecord.error=err(e);testRecord.override=wrapped&&wrapped.meta||testRecord.override;report.tests.push(testRecord);
            if(testRecord.override&&testRecord.override.restored===false)report.restored=false;
          }
        }

        const changed=report.tests.find(x=>x.responseDiff&&x.responseDiff.backendChanged);
        if(!report.registryUnchanged){
          report.conclusionHint="REGISTRY_CHANGED_ABORTED";
          report.conclusionNote="A no-op candidate write did not read back identically. Testing stopped immediately; use the Sidee backup/restore controls before any further write experiment.";
        }else if(changed){
          report.conclusionHint="IDENTIFIER_AFFECTS_WRITE_GATE";
          report.conclusionNote="A concrete identifier changed the response of the actual AppInfo fileWrite permission gate. This is direct evidence that the identifier participates in backend authorization.";
          report.interestingCandidate=changed.candidate;
        }else if(!report.candidateIdentifiers.length){
          report.conclusionHint="NO_REAL_IDENTIFIER_AVAILABLE";
          report.conclusionNote="No concrete non-empty identifier candidate was available from runtime/AppInfo/installed-app sources.";
        }else if(report.tests.length&&report.tests.every(x=>x.write&&Number(x.write.result.code)===Number(baselineGate.code)&&String(x.write.result.msg||"")===String(baselineGate.msg||"")&&x.override&&x.override.restored!==false)){
          report.conclusionHint="IDENTIFIER_STRING_NOT_SUFFICIENT";
          report.conclusionNote="Every tested concrete identifier reached the same AppConfig write rejection as baseline. For these candidates, changing only the identifier string is not sufficient.";
        }else if(!report.stoppedEarly){
          report.conclusionHint="INCONCLUSIVE";
          report.conclusionNote="Candidate tests completed without a decisive permission-gate difference.";
        }
      }
    }catch(e){
      report.error=err(e);
      if(report.conclusionHint==="INCONCLUSIVE")report.conclusionNote=report.error;
    }finally{
      state.report.identityWriteGateLab=report;
      renderIdentityWriteGateLab(report);
      log("Identity Write-Gate Lab complete",{baseline:report.baselineWrite&&report.baselineWrite.result,candidates:report.candidateIdentifiers.length,tested:report.tests.length,conclusion:report.conclusionHint,restored:report.restored,registryUnchanged:report.registryUnchanged,error:report.error||null});
      state.running=false;
      await save("identity-write-gate-lab");
    }
    return report;
  }

  async function candidatePermissionGateTest(){
    const input=$("identityPermissionIdentifier"),value=input?input.value.trim():"";
    if(!value)return set("candidatePermissionState","Enter a concrete identifier first. No install request was sent.");
    if(state.running)return;
    state.running=true;set("candidatePermissionState","Running explicit permission-gate test…");
    try{
      const wrapped=await withTemporaryServiceIdentifier(value,async()=>{
        const chosen=typeof window.Hisense_installApp_V2==="function"?"v2":"legacy";
        const test=await installCall(chosen);
        const verification=await verify();
        return {chosen:chosen,test:test,verification:verification};
      });
      const payload=wrapped.value,test=payload.test,verification=payload.verification,internal=test.trace&&test.trace.result||{ret:null,code:null,msg:null},status=gate(test,verification,state.report.installTest);
      const record={timestamp:new Date().toISOString(),identifier:value,override:wrapped.meta,method:payload.chosen,internal:internal,returnValue:test.returnValue,externalCallback:test.externalCallback,error:test.error,verification:verification,status:status,warning:"This was an explicit install permission request; if the permission gate passed, the target app may have been registered/installed."};
      state.report.candidatePermissionTest=record;
      if(state.report.identityOverrideLab){
        if(Number(internal.code)===503&&/permission|appconfig/i.test(String(internal.msg||""))){
          state.report.identityOverrideLab.conclusionHint="IDENTIFIER_STRING_NOT_SUFFICIENT";
          state.report.identityOverrideLab.conclusionNote="This concrete identifier still reached the AppConfig permission rejection. This conclusion applies to the tested identifier, not to every possible identity.";
        }else if(status==="CHANGED"||status==="PASSED"||verification.verified){
          state.report.identityOverrideLab.conclusionHint="IDENTIFIER_AFFECTS_BACKEND";
          state.report.identityOverrideLab.conclusionNote="The explicit permission-gate response changed for the tested identifier. Verification remains the only proof of installation.";
        }
        renderIdentityLab(state.report.identityOverrideLab);
      }
      set("candidatePermissionState",status+" · code "+String(internal.code)+" · "+(verification.verified?"VERIFIED INSTALLED":"not verified")+" · override restored "+(wrapped.meta.restored?"YES":"NO"));
      log("Candidate permission-gate test",record);await save("candidate-permission-gate-test");
    }catch(e){set("candidatePermissionState","Permission-gate test failed: "+err(e));log("Candidate permission-gate test failed",err(e));}
    finally{state.running=false;}
  }

  function syncTarget(){state.report.target=compact(target());}
  async function saveTarget(){syncTarget();try{const r=await fetch("/api/config",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({nuvio:target()})}),d=await r.json();if(!r.ok||!d.ok)throw new Error(d.error||"Could not save target");state.config.nuvio=d.nuvio;set("targetState","Target saved.");await save("target");}catch(e){set("targetState","Save failed: "+err(e));}}
  async function watchReportSync(sessionId){
    const token=++state.syncWatchToken;
    for(let i=0;i<24;i++){
      await new Promise(resolve=>setTimeout(resolve,750));
      if(token!==state.syncWatchToken)return;
      try{
        const r=await fetch("/api/reports/sync",{cache:"no-store"}),d=await r.json();
        if(!r.ok)continue;
        if(d.sessionId&&d.sessionId!==sessionId)continue;
        if(d.state==="SYNCED"){
          set("reportSaveState","Saved locally · GitHub synced to "+(d.branch||"sidee-reports")+".");
          return;
        }
        if(d.state==="ERROR"){
          set("reportSaveState","Saved locally · GitHub sync error: "+(d.message||"unknown error"));
          return;
        }
        if(d.state==="DISABLED"){
          set("reportSaveState","Saved locally · GitHub sync disabled.");
          return;
        }
        set("reportSaveState",d.state==="SYNCING"?"Saved locally · syncing to GitHub…":"Saved locally · GitHub sync queued.");
      }catch(e){}
    }
  }
  async function persist(reason){
    syncTarget();
    state.report.clientBuildId=CLIENT_BUILD_ID;
    state.report.updatedAt=new Date().toISOString();
    try{
      const r=await fetch("/api/reports/session",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({sessionId:state.report.sessionId,report:state.report,reason:reason||"autosave"})
      }),d=await r.json();
      if(!r.ok||!d.ok)throw new Error(d.error||"Report save failed");
      set("reportFileName",d.file);
      state.report.serverBuildId=d.serverBuildId||null;
      state.report.buildMatch=d.buildMatch===true;
      if(d.buildMatch===false){
        set("reportSaveState","STALE CLIENT · "+CLIENT_BUILD_ID+" ≠ "+(d.serverBuildId||"unknown")+" · reload Sidee before testing.");
        log("Client/server build mismatch",{clientBuildId:CLIENT_BUILD_ID,serverBuildId:d.serverBuildId});
        return d;
      }
      const sync=d.githubSync||{};
      if(sync.state==="DISABLED")set("reportSaveState","Saved locally · GitHub sync disabled.");
      else{
        set("reportSaveState",sync.state==="SYNCING"?"Saved locally · syncing to GitHub…":"Saved locally · GitHub sync queued.");
        watchReportSync(state.report.sessionId);
      }
      return d;
    }catch(e){
      set("reportSaveState","Report save failed: "+err(e));
      return {ok:false,error:err(e)};
    }
  }
  function save(reason){state.saveChain=state.saveChain.catch(()=>null).then(()=>persist(reason));return state.saveChain;}
  async function load(){
    const bust=Date.now();
    const responses=await Promise.all([fetch("/api/config?cb="+bust,{cache:"no-store"}),fetch("/api/status?cb="+bust,{cache:"no-store"})]);
    const d=await responses[0].json(),status=await responses[1].json();
    state.config=d;state.report.accessContext=pageContext();state.report.accessMode=accessMode();state.report.serverAccess={host:status.host||null,requestScheme:status.requestScheme||null,requestPort:status.requestPort||null};state.report.serverBuildId=status.clientBuildId||null;state.report.buildMatch=!!status.clientBuildId&&status.clientBuildId===CLIENT_BUILD_ID;
    if(state.report.buildMatch===false)log("Client/server build mismatch detected on load",{clientBuildId:CLIENT_BUILD_ID,serverBuildId:status.clientBuildId});
    const a=d.nuvio||{};$("appId").value=a.app_id||"nuviodebug";$("appName").value=a.app_name||"Nuvio TV";$("appUrl").value=a.app_url||"";$("iconUrl").value=a.icon_url||"";syncTarget();
  }

  function lastRemoteDiagnosticId(){
    try{return sessionStorage.getItem("sidee.remoteDiagnostic.lastRequest")||"";}catch(e){return "";}
  }
  function rememberRemoteDiagnosticId(id){
    try{sessionStorage.setItem("sidee.remoteDiagnostic.lastRequest",id);}catch(e){}
  }
  function renderRemoteDiagnosticState(text){
    set("remoteDiagnosticState",text);
    const btn=$("remoteDiagnosticArmBtn");
    if(btn)btn.textContent=state.remoteDiagnosticArmed?"Disable remote diagnostics":"Enable remote diagnostics for this page";
  }
  async function remoteDiagnosticAck(request,status,message){
    try{
      await fetch("/api/remote-diagnostic/ack",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({requestId:request.requestId,status:status,message:message||status})
      });
    }catch(e){}
  }
  async function runSafeRemoteDiagnostic(request){
    if(!state.remoteDiagnosticArmed||state.remoteDiagnosticRunning||state.running)return;
    if(!request||lastRemoteDiagnosticId()===request.requestId)return;
    state.remoteDiagnosticRunning=true;
    rememberRemoteDiagnosticId(request.requestId);
    const started=new Date().toISOString(),directNoop=request.workflow==="direct-appinfo-noop",identityWriteGate=request.workflow==="identity-write-gate";
    if((directNoop||identityWriteGate)&&request.requiresBuildId&&request.requiresBuildId!==CLIENT_BUILD_ID){
      renderRemoteDiagnosticState("ARMED · stale client for AppInfo write request");
      return;
    }
    state.report.remoteDiagnostic={
      lastRequestId:request.requestId,
      requestWorkflow:request.workflow||"safe-readonly",
      requestedBy:request.requestedBy||null,
      startedAt:started,
      completedAt:null,
      status:"RUNNING",
      workflow:directNoop?["direct-appinfo-write-noop","export"]:identityWriteGate?["baseline","identity-write-gate-lab","export"]:["baseline","context-identity-fingerprint","permission-source-trace","installed-metadata","verification","export"],
      error:null
    };
    renderRemoteDiagnosticState(directNoop?"RUNNING · backup-protected AppInfo no-op write":identityWriteGate?"RUNNING · identifier write-gate lab":"RUNNING · read-only diagnostic");
    await remoteDiagnosticAck(request,"RUNNING",directNoop?"TV accepted the armed AppInfo no-op write diagnostic":identityWriteGate?"TV accepted the armed identifier write-gate diagnostic":"TV accepted the armed read-only diagnostic");
    try{
      if(directNoop){
        const directResult=await directAppInfoWriteLab({remote:true});
        log("Remote AppInfo no-op result",{writeCapability:directResult&&directResult.writeCapability,backup:directResult&&directResult.backup&&directResult.backup.backupId});
      }else if(identityWriteGate){
        await baseline();
        const gateResult=await identityWriteGateLab({remote:true});
        log("Remote identifier write-gate result",{conclusion:gateResult&&gateResult.conclusionHint,tested:gateResult&&gateResult.tests&&gateResult.tests.length,interestingCandidate:gateResult&&gateResult.interestingCandidate||null});
      }else{
        await baseline();
        await contextIdentityFingerprint({remote:true});
        await permissionSourceTrace();
        await inspectInstalledMetadata();
        const verification=await verify();
        log("Remote diagnostic verification",verification);
      }
      state.report.remoteDiagnostic.completedAt=new Date().toISOString();
      state.report.remoteDiagnostic.status="COMPLETED";
      await save("remote-safe-diagnostic-complete");
      renderRemoteDiagnosticState("ARMED · last request completed");
      await remoteDiagnosticAck(request,"COMPLETED",directNoop?"AppInfo no-op write diagnostic completed":identityWriteGate?"Identifier write-gate diagnostic completed":"Read-only diagnostic completed");
    }catch(e){
      state.report.remoteDiagnostic.completedAt=new Date().toISOString();
      state.report.remoteDiagnostic.status="FAILED";
      state.report.remoteDiagnostic.error=err(e);
      await save("remote-safe-diagnostic-failed");
      renderRemoteDiagnosticState("ARMED · last request failed");
      await remoteDiagnosticAck(request,"FAILED",err(e));
    }finally{
      state.remoteDiagnosticRunning=false;
    }
  }
  async function pollRemoteDiagnostic(){
    try{
      const r=await fetch("/api/remote-diagnostic/request?clientBuildId="+encodeURIComponent(CLIENT_BUILD_ID),{cache:"no-store"}),d=await r.json();
      if(!r.ok)return;
      if(d.state==="PENDING"&&d.request){
        if(!state.remoteDiagnosticArmed){
          renderRemoteDiagnosticState("DISARMED · request waiting");
          return;
        }
        if(!state.running&&!state.remoteDiagnosticRunning)await runSafeRemoteDiagnostic(d.request);
      }else if(!state.remoteDiagnosticRunning){
        renderRemoteDiagnosticState(state.remoteDiagnosticArmed?"ARMED · waiting":"DISARMED");
      }
    }catch(e){
      if(!state.remoteDiagnosticRunning)renderRemoteDiagnosticState(state.remoteDiagnosticArmed?"ARMED · PC control offline":"DISARMED");
    }
  }
  function toggleRemoteDiagnostics(){
    state.remoteDiagnosticArmed=!state.remoteDiagnosticArmed;
    renderRemoteDiagnosticState(state.remoteDiagnosticArmed?"ARMED · waiting":"DISARMED");
    if(state.remoteDiagnosticArmed)pollRemoteDiagnostic();
  }
  function startRemoteDiagnosticPolling(){
    if(state.remoteDiagnosticTimer)return;
    renderRemoteDiagnosticState("DISARMED");
    state.remoteDiagnosticTimer=setInterval(pollRemoteDiagnostic,1500);
  }

  function controls(){return Array.prototype.slice.call(document.querySelectorAll("button,input,summary")).filter(el=>{if(!el||el.disabled||el.hidden)return false;const s=getComputedStyle(el);return s.display!=="none"&&s.visibility!=="hidden"&&el.getClientRects().length>0;});}
  function center(el){const r=el.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2};}
  function nextControl(cur,key,list){const from=center(cur);let best=null,score=Infinity;list.forEach(el=>{if(el===cur)return;const to=center(el),dx=to.x-from.x,dy=to.y-from.y;let p=null,c=0;if(key==="ArrowUp"&&dy<-4){p=-dy;c=Math.abs(dx);}if(key==="ArrowDown"&&dy>4){p=dy;c=Math.abs(dx);}if(key==="ArrowLeft"&&dx<-4){p=-dx;c=Math.abs(dy);}if(key==="ArrowRight"&&dx>4){p=dx;c=Math.abs(dy);}if(p===null)return;const s=p*10+c;if(s<score){score=s;best=el;}});return best;}
  window.addEventListener("keydown",e=>{const key=e.key||({13:"Enter",37:"ArrowLeft",38:"ArrowUp",39:"ArrowRight",40:"ArrowDown"}[e.keyCode]),active=document.activeElement;if((key==="Enter"||key==="OK")&&active&&(active.tagName==="BUTTON"||active.tagName==="SUMMARY")){e.preventDefault();active.click();return;}if(["ArrowUp","ArrowDown","ArrowLeft","ArrowRight"].indexOf(key)<0)return;if(active&&active.tagName==="INPUT"&&(key==="ArrowLeft"||key==="ArrowRight"))return;const list=controls();if(!list.length)return;const cur=list.indexOf(active)>=0?active:list[0],to=nextControl(cur,key,list);if(to){to.focus();e.preventDefault();}else if(list.indexOf(active)<0){cur.focus();e.preventDefault();}});

  $("remoteDiagnosticArmBtn").addEventListener("click",toggleRemoteDiagnostics);   $("baselineBtn").addEventListener("click",baseline); $("contextIdentityFingerprintBtn").addEventListener("click",()=>contextIdentityFingerprint()); $("runtimeContextInitBtn").addEventListener("click",initContext); $("clientInformationBtn").addEventListener("click",readClient); $("serviceTraceBtn").addEventListener("click",readTrace); $("directAppInfoWriteBtn").addEventListener("click",()=>directAppInfoWriteLab()); $("legacyHspdkWriteBtn").addEventListener("click",()=>legacyHspdkWriteLab()); $("addNuvioHspdkBtn").addEventListener("click",addNuvioHspdk); $("restoreHspdkBackupBtn").addEventListener("click",restoreHspdkBackup); $("addNuvioDirectBtn").addEventListener("click",addNuvioDirect); $("restoreAppInfoBackupBtn").addEventListener("click",restoreAppInfoBackup); $("identityOverrideLabBtn").addEventListener("click",()=>identityWriteGateLab()); $("candidatePermissionBtn").addEventListener("click",candidatePermissionGateTest); $("permissionSourceTraceBtn").addEventListener("click",permissionSourceTrace); $("installedMetadataBtn").addEventListener("click",inspectInstalledMetadata); $("installDiagnosticBtn").addEventListener("click",()=>installTest()); $("installLegacyBtn").addEventListener("click",()=>installTest("legacy")); $("installV2Btn").addEventListener("click",()=>installTest("v2")); $("temporaryIdentifierBtn").addEventListener("click",tempIdentifier); $("saveBtn").addEventListener("click",saveTarget); $("verifyBtn").addEventListener("click",async()=>{const r=await verify();log("Verification",r);await save("verification");}); $("reportBtn").addEventListener("click",()=>save("export"));
  load().then(async()=>{renderSummary();set("deviceBadge",typeof window.Hisense_GetFirmWareVersion==="function"?"VIDAA browser detected":"Waiting for VIDAA APIs");log("Sidee targeted identity diagnostic ready.");if(expectedInstalledAppContext())await contextIdentityFingerprint({automatic:true});startRemoteDiagnosticPolling();}).catch(e=>log("Config load failed",err(e)));
})();
