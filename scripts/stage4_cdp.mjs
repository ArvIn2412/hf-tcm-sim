import fs from 'node:fs';
const pages=await(await fetch(`http://127.0.0.1:${process.env.HF_TCM_CDP_PORT||9240}/json/list`)).json();
const baseURL=process.env.HF_TCM_QA_BASE_URL||'http://127.0.0.1:18772';
const page=pages.find(p=>p.type==='page'&&p.url.startsWith(baseURL+'/scientific'));
if(!page)throw Error('No localhost scientific lab target; refusing to control an unrelated page');
const ws=new WebSocket(page.webSocketDebuggerUrl);
await new Promise(r=>ws.addEventListener('open',r,{once:true}));
let id=0; const pending=new Map();
export const errors=[];
ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails);if(m.id){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(m.error):p.resolve(m.result);}};
ws.addEventListener('close',()=>{for(const p of pending.values())p.reject(Error('CDP target closed'));pending.clear();});
export const send=(method,params={})=>new Promise((resolve,reject)=>{if(method==='Page.navigate'&&params.url?.startsWith('http://127.0.0.1:18772/'))params={...params,url:baseURL+params.url.slice('http://127.0.0.1:18772'.length)};const n=++id;const timeout=setTimeout(()=>{pending.delete(n);reject(Error('CDP command timed out: '+method));},30000);pending.set(n,{resolve:value=>{clearTimeout(timeout);resolve(value);},reject:error=>{clearTimeout(timeout);reject(error);}});ws.send(JSON.stringify({id:n,method,params}));});
export const js=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;};
export const pause=ms=>new Promise(r=>setTimeout(r,ms));
export async function until(expression,timeout=30000){const start=Date.now();while(Date.now()-start<timeout){if(await js(expression))return Date.now()-start;await pause(70);}throw Error('Timeout: '+expression);}
export const close=()=>ws.close();
export async function screenshot(path){const {data}=await send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path,Buffer.from(data,'base64'));}
await send('Page.enable'); await send('Runtime.enable');
