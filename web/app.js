(() => {
  "use strict";

  const $ = id => document.getElementById(id);
  const SESSION_RE = /^sidee-\d{8}-\d{6}-[a-f0-9]{4}$/;
  const CLIENT_KEYS = /(app|identifier|appid|role|customer|origin|url|permission|appconfig|store|package|security)/i;
  const logBox = $("console");
  const state = { config:null, report:null, running:false, saveChain:Promise.resolve(), syncWatchToken:0 };

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
  function newReport(){ const now=new Date().toISOString(); return {sessionId:sessionId(),startedAt:now,updatedAt:now,device:{},baseline:null,contextInit:{status:"NOT_RUN",available:false,before:null,after:null,diff:null},clientInformation:null,serviceTrace:[],permissionSourceTrace:null,installTest:null,verification:null,installedAppMetadata:null,target:{},temporaryIdentifierTest:null,summary:{runtimeIdentity:"MISSING",contextInit:"NOT_RUN",permissionGate:"UNKNOWN"}}; }
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
          if(url&&url.pathname==="/app.js"){entry.status="SIDEE_SELF_SKIPPED";}
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
    state.report.updatedAt=new Date().toISOString();
    try{
      const r=await fetch("/api/reports/session",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({sessionId:state.report.sessionId,report:state.report,reason:reason||"autosave"})
      }),d=await r.json();
      if(!r.ok||!d.ok)throw new Error(d.error||"Report save failed");
      set("reportFileName",d.file);
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
  async function load(){const r=await fetch("/api/config",{cache:"no-store"}),d=await r.json();state.config=d;const a=d.nuvio||{};$("appId").value=a.app_id||"nuviodebug";$("appName").value=a.app_name||"Nuvio TV";$("appUrl").value=a.app_url||"";$("iconUrl").value=a.icon_url||"";syncTarget();}

  function controls(){return Array.prototype.slice.call(document.querySelectorAll("button,input,summary")).filter(el=>{if(!el||el.disabled||el.hidden)return false;const s=getComputedStyle(el);return s.display!=="none"&&s.visibility!=="hidden"&&el.getClientRects().length>0;});}
  function center(el){const r=el.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2};}
  function nextControl(cur,key,list){const from=center(cur);let best=null,score=Infinity;list.forEach(el=>{if(el===cur)return;const to=center(el),dx=to.x-from.x,dy=to.y-from.y;let p=null,c=0;if(key==="ArrowUp"&&dy<-4){p=-dy;c=Math.abs(dx);}if(key==="ArrowDown"&&dy>4){p=dy;c=Math.abs(dx);}if(key==="ArrowLeft"&&dx<-4){p=-dx;c=Math.abs(dy);}if(key==="ArrowRight"&&dx>4){p=dx;c=Math.abs(dy);}if(p===null)return;const s=p*10+c;if(s<score){score=s;best=el;}});return best;}
  window.addEventListener("keydown",e=>{const key=e.key||({13:"Enter",37:"ArrowLeft",38:"ArrowUp",39:"ArrowRight",40:"ArrowDown"}[e.keyCode]),active=document.activeElement;if((key==="Enter"||key==="OK")&&active&&(active.tagName==="BUTTON"||active.tagName==="SUMMARY")){e.preventDefault();active.click();return;}if(["ArrowUp","ArrowDown","ArrowLeft","ArrowRight"].indexOf(key)<0)return;if(active&&active.tagName==="INPUT"&&(key==="ArrowLeft"||key==="ArrowRight"))return;const list=controls();if(!list.length)return;const cur=list.indexOf(active)>=0?active:list[0],to=nextControl(cur,key,list);if(to){to.focus();e.preventDefault();}else if(list.indexOf(active)<0){cur.focus();e.preventDefault();}});

  $("baselineBtn").addEventListener("click",baseline); $("runtimeContextInitBtn").addEventListener("click",initContext); $("clientInformationBtn").addEventListener("click",readClient); $("serviceTraceBtn").addEventListener("click",readTrace); $("permissionSourceTraceBtn").addEventListener("click",permissionSourceTrace); $("installedMetadataBtn").addEventListener("click",inspectInstalledMetadata); $("installDiagnosticBtn").addEventListener("click",()=>installTest()); $("installLegacyBtn").addEventListener("click",()=>installTest("legacy")); $("installV2Btn").addEventListener("click",()=>installTest("v2")); $("temporaryIdentifierBtn").addEventListener("click",tempIdentifier); $("saveBtn").addEventListener("click",saveTarget); $("verifyBtn").addEventListener("click",async()=>{const r=await verify();log("Verification",r);await save("verification");}); $("reportBtn").addEventListener("click",()=>save("export"));
  load().then(()=>{renderSummary();set("deviceBadge",typeof window.Hisense_GetFirmWareVersion==="function"?"VIDAA browser detected":"Waiting for VIDAA APIs");log("Sidee targeted identity diagnostic ready.");}).catch(e=>log("Config load failed",err(e)));
})();
