/* Small shared reader: current release + only the selected language/index/profile.
 * Public clients read GCS objects, never the authenticated admin API.
 */
'use strict';
const params=new URLSearchParams(location.search);
const lang=params.get('lang')==='en'?'en':'zh', id=params.get('id'), draft=params.get('draft')==='1';
const el=id=>document.getElementById(id);
const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
const validId=value=>/^[a-z0-9][a-z0-9-]{0,79}$/.test(value);
let bytes=0, requests=0;
function urlFor(values){const p=new URLSearchParams(values);return '?'+p.toString();}
el('directory-link').href=urlFor({lang});
el('language-link').href=urlFor({lang:lang==='zh'?'en':'zh',...(id?{id}:{}),...(draft?{draft:'1'}:{})});
el('language-link').textContent=lang==='zh'?'English':'中文';
document.documentElement.lang=lang==='zh'?'zh-Hant':'en';
function safeURL(value){try{const u=new URL(value);return ['https:','http:'].includes(u.protocol)?u.href:'';}catch{return '';}}
function photo(data){const img=node('img');img.src=safeURL(data.photo);img.alt=data.name;img.width=180;img.height=180;img.loading='lazy';img.addEventListener('error',()=>img.hidden=true,{once:true});return img;}
function renderProfile(d){if(d.id!==id||d.lang!==lang||typeof d.bodyHtml!=='string')throw Error('資料格式不符 / Invalid profile');el('page-title').textContent=d.name;document.title=d.name+'｜NTU Journalism';const header=node('section',undefined,'profile-heading');header.append(photo(d));const info=node('div');info.append(node('h2',d.title));for(const k of ['email','phone','office','expertise'])if(d[k])info.append(node('p',d[k]));if(safeURL(d.website)){const a=node('a',lang==='zh'?'個人網站':'Personal website');a.href=d.website;a.rel='noopener';info.append(a);}header.append(info);const body=node('article',undefined,'profile-body');body.id='faculty-biography';body.innerHTML=d.bodyHtml;el('faculty-content').replaceChildren(header,body);}
function renderIndex(d){if(d.lang!==lang||!Array.isArray(d.items))throw Error('資料格式不符 / Invalid directory');el('page-title').textContent=lang==='zh'?'師資名單':'Faculty directory';const grid=node('div',undefined,'faculty-grid');for(const item of d.items){if(!validId(item.id))throw Error('Invalid faculty ID');const card=node('article',undefined,'faculty-card');const a=node('a',item.name);a.href=urlFor({id:item.id,lang});card.append(photo(item),node('h2'));card.lastChild.append(a);card.append(node('p',item.title));grid.append(card);}el('faculty-content').replaceChildren(grid);}
async function read(url,count=true){const response=await fetch(url,{signal:AbortSignal.timeout(12000)});if(!response.ok)throw Error(lang==='zh'?'資料暫時無法讀取（'+response.status+'）':'Data unavailable ('+response.status+')');const raw=await response.text();if(count){bytes+=new TextEncoder().encode(raw).length;requests++;}return JSON.parse(raw);}
async function start(){bytes=0;requests=0;el('retry').hidden=true;el('status').textContent=lang==='zh'?'載入中…':'Loading…';const begin=performance.now();try{if(id&&!validId(id))throw Error('Invalid faculty ID');if(draft&&id){renderProfile(await read('/faculty/api/preview/'+id+'/'+lang));}else{const feed=document.documentElement.dataset.facultyFeed;if(!feed)throw Error('Missing faculty feed configuration');const base=new URL(feed,location.origin);const current=await read(new URL('current.json',base));if(!/^[a-f0-9]{64}$/.test(current.release))throw Error('Invalid release');const filename=id?id+'.'+lang+'.json':'index.'+lang+'.json';const data=await read(new URL('releases/'+current.release+'/'+filename,base));id?renderProfile(data):renderIndex(data);}el('status').textContent=draft?'已儲存草稿 / Saved draft':'';el('metrics').textContent=`${requests} 次資料請求 · ${(bytes/1024).toFixed(1)} KB 解碼後文字 · ${(performance.now()-begin).toFixed(0)} ms 至內容呈現（本次測量，不含照片完成時間）`;}catch(e){el('status').textContent=e.message;el('retry').hidden=false;}}
el('retry').addEventListener('click',start);start();
