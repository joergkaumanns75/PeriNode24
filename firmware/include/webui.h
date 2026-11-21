// Weboberfläche des Perinode24-Laders – vollständig eingebettet (keine externen Ressourcen,
// funktioniert auch im Access-Point-Modus ohne Internet).
#pragma once
static const char INDEX_HTML[] = R"rawliteral(<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Perinode24 Lader</title>
<style>
:root{--bg:#f4f5f7;--card:#fff;--fg:#1d2330;--mut:#6b7280;--line:#e3e6eb;--acc:#2563eb;
--s0:#9ca3af;--s1:#d97706;--s2:#2563eb;--s3:#7c3aed;--s4:#16a34a;--s5:#22c55e;--s6:#dc2626;--s7:#6b7280}
@media (prefers-color-scheme:dark){:root{--bg:#12151b;--card:#1b2029;--fg:#e6e9ef;--mut:#9aa3b2;--line:#2a313d;--acc:#60a5fa}}
*{box-sizing:border-box}body{margin:0;font:15px/1.4 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--fg)}
header{display:flex;flex-wrap:wrap;gap:8px 20px;align-items:baseline;padding:14px 16px;border-bottom:1px solid var(--line);background:var(--card)}
h1{font-size:18px;margin:0 auto 0 0}header span{color:var(--mut);font-size:13px}header b{color:var(--fg);font-weight:600}
main{max-width:1200px;margin:0 auto;padding:16px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;cursor:pointer}
.card.sel{outline:2px solid var(--acc)}
.top{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.top h2{font-size:15px;margin:0}
.badge{font-size:12px;font-weight:600;color:#fff;padding:2px 9px;border-radius:99px;white-space:nowrap}
.big{font-size:28px;font-weight:650;font-variant-numeric:tabular-nums}.big small{font-size:14px;color:var(--mut);font-weight:400}
.kv{display:grid;grid-template-columns:auto 1fr;gap:2px 12px;font-size:13px;margin-top:6px;font-variant-numeric:tabular-nums}
.kv span{color:var(--mut)}
.err{color:var(--s6);font-size:13px;margin-top:6px;min-height:18px}
.btns{display:flex;gap:8px;margin-top:8px}
button{font:inherit;font-size:13px;padding:6px 12px;border-radius:7px;border:1px solid var(--line);background:transparent;color:var(--fg);cursor:pointer}
button.pri{background:var(--acc);border-color:var(--acc);color:#fff}button:disabled{opacity:.4;cursor:default}
section{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;margin-top:14px}
section h3{font-size:15px;margin:0 0 10px}
svg{width:100%;height:240px;display:block}svg text{fill:var(--mut);font-size:11px}
.legend{display:flex;gap:16px;font-size:12px;color:var(--mut)}.legend i{display:inline-block;width:12px;height:3px;margin-right:5px;vertical-align:middle}
form{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px 16px}
label{font-size:13px;color:var(--mut);display:flex;flex-direction:column;gap:3px}
input{font:inherit;padding:6px 8px;border:1px solid var(--line);border-radius:7px;background:var(--bg);color:var(--fg);width:100%}
.row{grid-column:1/-1;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.msg{font-size:13px;color:var(--mut)}
details summary{cursor:pointer;font-weight:600}
.admin{margin:0 0 14px;padding:10px 14px}.admin form{grid-template-columns:minmax(220px,320px) 1fr;align-items:end}.admin .row{grid-column:auto}
</style></head><body>
<header><h1>Perinode24 Lader</h1>
<span>Bus <b id="vbus">–</b></span><span>WLAN <b id="wifi">–</b></span><span>Laufzeit <b id="up">–</b></span>
<span id="conn"></span></header>
<main>
<section class="admin"><form id="af"><label>Admin-Passwort (für Schalten und Einstellungen)<input id="pw" type="password" autocomplete="current-password"></label>
<div class="row"><button type="button" id="rall">Alle Fehler quittieren</button><span class="msg" id="amsg"></span></div></form></section>
<div class="grid" id="grid"></div>
<section><div class="top"><h3 id="chtitle">Verlauf Akku 1 (2 h)</h3>
<div class="legend"><span><i style="background:var(--s2)"></i>Spannung</span><span><i style="background:var(--s1)"></i>Strom</span></div></div>
<svg id="chart" viewBox="0 0 800 240" preserveAspectRatio="none"></svg></section>
<section><details><summary>Ladeparameter</summary><p class="msg">Werte bei 20 °C, Spannung wird mit dem Temperaturkoeffizienten kompensiert. Datenblatt des Akkus beachten.</p>
<form id="pf">
<label>Ladeschlussspannung [V] (13,8–14,8)<input name="vAbs" type="number" step="0.01"></label>
<label>Erhaltungsspannung [V] (13,2–13,9)<input name="vFloat" type="number" step="0.01"></label>
<label>Temperaturkoeffizient [mV/K] (−30…0)<input name="tk" type="number" step="0.1"></label>
<label>Ladestrom [A] (0,10–0,72)<input name="iBulk" type="number" step="0.01"></label>
<label>Vorladestrom [A]<input name="iPre" type="number" step="0.01"></label>
<label>Umschaltstrom Erhaltung [A]<input name="iTerm" type="number" step="0.001"></label>
<label>Nachladeschwelle [A]<input name="iRebulk" type="number" step="0.01"></label>
<label>Max. Akkutemperatur [°C] (30–50)<input name="tMax" type="number" step="0.5"></label>
<label>Max. Dauer Konstantspannung [h] (1–8)<input name="hAbsMax" type="number" step="0.5"></label>
<label>Max. Ladezeit gesamt [h] (4–16)<input name="hChgMax" type="number" step="0.5"></label>
<div class="row"><button type="submit" class="pri">Speichern</button><span class="msg" id="pmsg"></span></div>
</form></details></section>
<section><details><summary>WLAN und Passwort</summary>
<form id="wf">
<label>WLAN-Name (SSID, leer = nur Access Point)<input name="ssid" autocomplete="off"></label>
<label>WLAN-Passwort (leer = unverändert)<input name="pass" type="password" autocomplete="new-password"></label>
<label>Neues Admin-Passwort (optional, mind. 8 Zeichen)<input name="newpw" type="password" autocomplete="new-password"></label>
<div class="row"><button type="submit" class="pri">Speichern und neu starten</button><span class="msg" id="wmsg"></span></div>
</form></details></section>
</main>
<script>
const $=s=>document.querySelector(s);
const COL=['var(--s0)','var(--s1)','var(--s2)','var(--s3)','var(--s4)','var(--s5)','var(--s6)','var(--s7)'];
let sel=0,last=null;
try{sel=+localStorage.getItem('p24sel')||0;$('#pw').value=sessionStorage.getItem('p24pw')||''}catch(e){}
$('#pw').addEventListener('input',e=>{try{sessionStorage.setItem('p24pw',e.target.value)}catch(_){}});
const f=(v,d)=>v==null?'–':v.toFixed(d).replace('.',',');
const dur=s=>s<60?s+' s':s<3600?Math.floor(s/60)+' min':Math.floor(s/3600)+' h '+String(Math.floor(s%3600/60)).padStart(2,'0')+' min';
async function post(url,data){
  const b=new URLSearchParams(data);b.set('pw',$('#pw').value);
  try{const r=await fetch(url,{method:'POST',body:b});const j=await r.json().catch(()=>({}));
    return {ok:r.ok&&j.ok!==false,msg:j.msg||(r.ok?'OK':'Fehler '+r.status)}}
  catch(e){return {ok:false,msg:'Keine Verbindung'}}
}
function card(c,k){
  const d=document.createElement('div');d.className='card'+(k==sel?' sel':'');
  d.innerHTML=`<div class="top"><h2>Akku ${k+1}</h2><span class="badge" style="background:${COL[c.st]}">${c.name}</span></div>
  <div class="big">${f(c.v,2)} <small>V</small> &nbsp;${f(c.i,3)} <small>A</small></div>
  <div class="kv"><span>Temperatur</span><div>${c.t==null?'kein Sensor':f(c.t,1)+' °C'}</div>
  <span>Sollspannung</span><div>${c.vt?f(c.vt,2)+' V':'–'}</div>
  <span>Geladen</span><div>${f(c.ah*1000,0)} mAh</div>
  <span>In Phase seit</span><div>${dur(c.ts)}</div></div>
  <div class="err">${c.err||''}</div>
  <div class="btns"><button data-a="reset" ${c.st!=6?'disabled':''}>Quittieren</button>
  <button data-a="${c.en?'disable':'enable'}">${c.en?'Ausschalten':'Einschalten'}</button></div>`;
  d.onclick=e=>{const a=e.target.dataset&&e.target.dataset.a;
    if(a){e.stopPropagation();post('/api/cmd',{action:a,ch:k}).then(r=>{$('#amsg').textContent=r.msg;poll()});return}
    sel=k;try{localStorage.setItem('p24sel',k)}catch(_){}render();hist()};
  return d;
}
function render(){
  if(!last)return;const g=$('#grid');g.replaceChildren(...last.ch.map(card));
  $('#chtitle').textContent='Verlauf Akku '+(sel+1)+' (2 h)';
}
async function poll(){
  try{const r=await fetch('/api/status');last=await r.json();
    $('#vbus').textContent=f(last.vbus,1)+' V';
    const w=last.wifi;$('#wifi').textContent=w.sta?(w.ssid+' '+w.ip+' ('+w.rssi+' dBm)'):(w.ap?'Access Point':'getrennt');
    $('#up').textContent=dur(last.up);$('#conn').textContent='';render();
  }catch(e){$('#conn').textContent='⚠ keine Verbindung'}
}
async function hist(){
  try{const r=await fetch('/api/history?ch='+sel);draw(await r.json())}catch(e){}
}
function draw(h){
  const W=800,H=240,L=44,R=44,T=10,B=24,n=h.v.length,svg=$('#chart');
  const x=i=>L+(n<2?0:i*(W-L-R)/(Math.max(n,2)-1));
  const vy=v=>T+(1-(v-10)/5)*(H-T-B), iy=i=>T+(1-i/0.8)*(H-T-B);
  let s='';
  for(let v=10;v<=15;v++){s+=`<line x1="${L}" x2="${W-R}" y1="${vy(v)}" y2="${vy(v)}" stroke="var(--line)"/><text x="${L-6}" y="${vy(v)+4}" text-anchor="end">${v} V</text>`}
  for(let i=0;i<=0.8;i+=0.2){s+=`<text x="${W-R+6}" y="${iy(i)+4}">${i.toFixed(1).replace('.',',')} A</text>`}
  const span=n*h.step/60;s+=`<text x="${L}" y="${H-6}">−${Math.round(span)} min</text><text x="${W-R}" y="${H-6}" text-anchor="end">jetzt</text>`;
  if(n>1){
    const pv=h.v.map((v,i)=>x(i)+','+vy(Math.min(15,Math.max(10,v/1000)))).join(' ');
    const pi=h.i.map((v,i)=>x(i)+','+iy(Math.min(0.8,Math.max(0,v/1000)))).join(' ');
    s+=`<polyline points="${pi}" fill="none" stroke="var(--s1)" stroke-width="2" vector-effect="non-scaling-stroke"/>`;
    s+=`<polyline points="${pv}" fill="none" stroke="var(--s2)" stroke-width="2" vector-effect="non-scaling-stroke"/>`;
  }else s+=`<text x="${W/2}" y="${H/2}" text-anchor="middle">Noch keine Messwerte</text>`;
  svg.innerHTML=s;
}
async function loadParams(){
  try{const p=await (await fetch('/api/params')).json();
    for(const el of $('#pf').elements)if(el.name&&p[el.name]!=null)el.value=p[el.name];
    $('#wf').elements.ssid.value=p.ssid||''}catch(e){}
}
$('#pf').onsubmit=async e=>{e.preventDefault();const r=await post('/api/params',Object.fromEntries(new FormData(e.target)));
  $('#pmsg').textContent=r.msg;if(r.ok)loadParams()};
$('#wf').onsubmit=async e=>{e.preventDefault();const r=await post('/api/wifi',Object.fromEntries(new FormData(e.target)));$('#wmsg').textContent=r.msg};
$('#rall').onclick=async()=>{const r=await post('/api/cmd',{action:'reset',ch:'all'});$('#amsg').textContent=r.msg;poll()};
poll();hist();loadParams();setInterval(poll,2000);setInterval(hist,30000);
</script></body></html>)rawliteral";
