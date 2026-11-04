/* Stage 7 prototype pages. Markup mirrors the TSX 1:1 (Settings, Diagnostics, About, Licenses). State comes from the URL. */
Object.assign(PA,{
Bug:'<path d="m8 2 1.88 1.88"/><path d="M14.12 3.88 16 2"/><path d="M9 7.13v-1a3.003 3.003 0 1 1 6 0v1"/><path d="M12 20c-3.3 0-6-2.7-6-6v-3a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v3c0 3.3-2.7 6-6 6"/><path d="M12 20v-9"/><path d="M6.53 9C4.6 8.8 3 7.1 3 5"/><path d="M6 13H2"/><path d="M3 21c0-2.1 1.7-3.9 3.8-4"/><path d="M20.97 5c0 2.1-1.6 3.8-3.5 4"/><path d="M22 13h-4"/><path d="M17.2 17c2.1.1 3.8 1.9 3.8 4"/>',
Heart:'<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/>',
Coffee:'<path d="M10 2v2"/><path d="M14 2v2"/><path d="M16 8a1 1 0 0 1 1 1v8a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4V9a1 1 0 0 1 1-1h14a4 4 0 1 1 0 8h-1"/><path d="M6 2v2"/>',
Download:'<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>',
FileText:'<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/>',
Github:'<path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4"/><path d="M9 18c-4.51 2-5-2-7-2"/>',
Clock:'<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
Wrench:'<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>',
Sparkles:'<path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/><path d="M20 3v4"/><path d="M22 5h-4"/><path d="M4 17v2"/><path d="M5 18H3"/>',
Minus:'<path d="M5 12h14"/>',ArrowLeft:'<path d="m12 19-7-7 7-7"/><path d="M19 12H5"/>'});
const PG=P('page','settings');
let DIAG='';
const NT=()=>`<span class="ab-ext" aria-hidden="true">${I('ExternalLink',16)}</span><span class="visually-hidden">${t('about.externalLink')}</span>`;
const spin=(c='spinner-small')=>`<span class="${c}" aria-hidden="true"></span>`;

/* ---------- Settings ---------- */
function settingsHtml(){
 const s=P('s','ok');
 if(s==='loading')return `<div class="st st--state"><h1 class="visually-hidden">${t('settings.title')}</h1><div class="ui-state" role="status" aria-live="polite" aria-label="${t('common.loading')}"><div class="spinner" aria-hidden="true"></div><p>${t('settings.loading')}</p></div></div>`;
 if(s==='error')return `<div class="st st--state"><h1 class="visually-hidden">${t('settings.title')}</h1><div class="ui-state ui-state--error" role="alert"><div class="ui-state-icon" aria-hidden="true">${I('Alert',32)}</div><h2>${t('settings.errorTitle')}</h2><p>Der Server antwortet nicht. Prüfen Sie, ob OpenCloudTouch läuft, und versuchen Sie es erneut.</p><button class="btn btn-primary">${t('common.retry')}</button></div></div>`;
 const sc=P('sc','idle')==='scanning',ip=P('ip','none'),lv=P('lv','idle')==='saving',dl=P('dl','idle');
 const ipv=ip==='format'?'192.168.1':ip==='probe'||ip==='probing'?'192.168.1.99':'';
 const err=ip==='empty'?t('settings.manualIps.enterIp'):ip==='format'?t('settings.manualIps.invalidFormat'):ip==='probe'?t('settings.manualIps.probeError',{ip:'192.168.1.99'}):'';
 const probing=ip==='probing';
 const msg=err?`<div id="ip-error" class="ui-field-error" role="alert">${I('CircleX',16)}<span>${esc(err)}</span></div>`:`<p id="ip-hint" class="ui-field-hint">${t('settings.manualIps.hint')}</p>`;
 return `<div class="st"><h1 class="ui-h1">${t('settings.title')}</h1>
<section class="st-section" aria-labelledby="st-discovery-title"><h2 id="st-discovery-title" class="ui-h2 st-h2"><span class="st-h2-icon" aria-hidden="true">${I('Search',22)}</span>${t('settings.deviceDiscovery.sectionTitle')}</h2>
<div class="ui-card st-card"><div class="st-method"><h3 class="ui-h3">${t('settings.deviceDiscovery.autoTitle')}</h3><p class="st-text">${t('settings.deviceDiscovery.autoDescription')}</p>
<button type="button" class="btn btn-primary st-scan" ${sc?'disabled aria-busy="true"':'aria-busy="false"'}>${sc?spin()+t('settings.deviceDiscovery.scanning'):I('Search',18)+t('settings.deviceDiscovery.scanButton')}</button><span class="visually-hidden" role="status">${sc?t('settings.deviceDiscovery.scanningStatus'):''}</span></div>
<div class="st-method"><h3 class="ui-h3">${t('settings.deviceDiscovery.manualTitle')}</h3><p class="st-text">${t('settings.deviceDiscovery.manualDescription')}</p>
<form class="ui-field st-ip" novalidate onsubmit="return false"><label for="ip-input" class="ui-label">${t('settings.manualIps.label')}</label><div class="st-ip-row"><input id="ip-input" type="text" class="ui-input" value="${ipv}" placeholder="${t('settings.manualIps.placeholder')}" autocomplete="off" autocapitalize="off" spellcheck="false" ${err?'aria-invalid="true" aria-describedby="ip-error"':'aria-describedby="ip-hint"'} ${probing?'disabled':''}><button type="submit" class="btn btn-primary st-add" ${probing?'disabled aria-busy="true"':'aria-busy="false"'}>${probing?spin()+t('settings.manualIps.probing'):t('settings.manualIps.addButton')}</button></div><div class="st-ip-msg">${msg}</div></form></div></div></section>
<section class="st-section" aria-labelledby="st-logging-title"><h2 id="st-logging-title" class="ui-h2 st-h2"><span class="st-h2-icon" aria-hidden="true">${I('FileText',22)}</span>${t('settings.logging.sectionTitle')}</h2>
<div class="ui-card st-card"><p class="st-text">${t('settings.logging.description')}</p>
<div class="ui-field st-level"><label for="log-level-select" class="ui-label">${t('settings.logging.logLevel')}</label><div class="st-select"><select id="log-level-select" class="ui-select" ${lv?'disabled aria-busy="true"':''}><option value="CRITICAL">${t('settings.logging.levelOff')}</option><option value="INFO" selected>${t('settings.logging.levelInfo')}</option><option value="DEBUG">${t('settings.logging.levelDebug')}</option></select><span class="st-select-icon" aria-hidden="true">${lv?`<span class="ui-spin">${I('Loader',18)}</span>`:I('ChevronDown',18)}</span></div><span class="visually-hidden" role="status">${lv?t('settings.logging.levelSaving'):''}</span></div>
<div class="st-download"><p class="st-text">${t('settings.logging.downloadDescription')}</p><button type="button" class="btn btn-secondary st-download-btn" ${dl==='busy'?'disabled aria-busy="true"':'aria-busy="false"'}>${dl==='busy'?spin()+t('settings.logging.downloading'):I('Download',18)+t('settings.logging.downloadLogs')}</button>${dl==='error'?`<div class="wz-status wz-status--error st-download-error" role="alert"><span class="wz-icon" aria-hidden="true">${I('CircleX',20)}</span><div class="wz-status-body"><p>${esc(t('settings.logging.downloadFailed',{error:'HTTP 500'}))}</p></div></div>`:''}</div></div></section></div>`}

/* ---------- Diagnostics ---------- */
const SETUP=['unconfigured','pending','configured','failed','outdated','offline','unknown'];
const SBI={unconfigured:['Alert','warning'],pending:['Hourglass','info'],configured:['CircleCheck','success'],failed:['CircleX','danger'],outdated:['RefreshCw','warning'],offline:['WifiOff','neutral'],unknown:['CircleHelp','neutral']};
const PRES={green:['success','CircleCheck','diagnostics.statusOnline'],yellow:['warning','Clock','diagnostics.statusStale'],red:['danger','WifiOff','diagnostics.statusOffline']};
const presence=ls=>{if(!ls)return'red';const d=Date.now()-new Date(ls).getTime();return d<3e5?'green':d<18e5?'yellow':'red'};
const badge=(v,ic,txt,size='')=>`<span class="ui-badge ui-badge--${v}${size}"><span class="ui-badge-icon" aria-hidden="true">${I(ic,14)}</span><span>${esc(txt)}</span></span>`;
const row=(l,v,mono)=>`<div class="dg-row"><dt>${l}</dt><dd${mono?' class="ui-mono"':''}>${v}</dd></div>`;
const NAMESD=['Wohnzimmer','Küche','Schlafzimmer','Büro','Bad','Terrasse','Keller','Flur','Gästezimmer','Schlafzimmer Obergeschoss Süd Lautsprecher Anbau Neu1'];
function diagDevices(n){const now=Date.now(),off=[60e3,10*60e3,3*3600e3,null,2*60e3,20*60e3,26*3600e3,null,4*60e3,29*60e3];
 return Array.from({length:n},(_,i)=>({name:NAMESD[i%NAMESD.length],model:['SoundTouch 30','SoundTouch 10','SoundTouch 20','SoundTouch 300'][i%4],ip:'192.168.178.'+(20+i),fw:i%3===0?'27.0.6.46330.5043500 epdbuild.trunk.hepdswbld04.2022-08-04T11:20:29':'27.0.6.46330.5043500',st:i===9?'complete':SETUP[i%7],ls:off[i%10]==null?null:new Date(now-off[i%10]).toISOString(),ssh:i%2===0}))}
function diagHtml(){
 const s=P('s','ok'),h1=`<h1 class="ui-h1">${t('diagnostics.title')}</h1>`;
 if(s==='loading')return `<div class="dg"><a href="#" class="pg-back"><span aria-hidden="true">${I('ArrowLeft',18)}</span><span>${t('about.back')}</span></a>${h1}<div class="ui-state" role="status" aria-live="polite"><div class="spinner" aria-hidden="true"></div><p>${t('common.loading')}</p></div></div>`;
 if(s==='error')return `<div class="dg"><a href="#" class="pg-back"><span aria-hidden="true">${I('ArrowLeft',18)}</span><span>${t('about.back')}</span></a>${h1}<div class="ui-state ui-state--error" role="alert"><div class="ui-state-icon" aria-hidden="true">${I('CircleX',32)}</div><p>Network failure: GET /api/diagnostics 502 Bad Gateway</p></div></div>`;
 const nodev=s==='nodev',n=nodev?0:+P('n',10),busy=P('dl','idle')==='busy',lg=P('long','0')==='1';
 const plat=lg?'Linux-6.1.0-18-amd64-x86_64-with-glibc2.36-Debian-GNU/Linux-12-bookworm-container-docker-overlay2-aarch64-qemu-emulated':'Linux-6.1.0-18-amd64';
 const devs=diagDevices(n);
 const devHtml=nodev?`<p class="ui-card dg-empty"><span aria-hidden="true">${I('Speaker',22)}</span>${t('diagnostics.noDevices')}</p>`:`<div class="dg-devices">${devs.map(d=>{const p=PRES[presence(d.ls)],sk=SETUP.includes(d.st)?d.st:'unknown',sb=SBI[sk];return `<article class="ui-card dg-device"><div class="dg-device-head"><div class="dg-device-title"><h3 class="ui-h3">${esc(d.name)}</h3><span class="ui-small">${d.model}</span></div>${badge(p[0],p[1],t(p[2]))}</div><dl class="dg-kv dg-kv--compact">${row(t('diagnostics.ip'),d.ip,1)}${row(t('diagnostics.firmware'),d.fw,1)}${row(t('diagnostics.setupStatus'),badge(sb[1],sb[0],t('statusBadge.'+sk),' ui-badge--small'))}${row(t('diagnostics.lastSeen'),d.ls?new Date(d.ls).toLocaleString('de-DE'):`<span aria-hidden="true">—</span><span class="visually-hidden">${t('diagnostics.unknownValue')}</span>`)}${row(t('diagnostics.ssh'),d.ssh?badge('success','Check',t('diagnostics.sshOn')):badge('','Minus',t('diagnostics.sshOff')))}</dl></article>`}).join('')}</div>`;
 return `<div class="dg" data-test="diagnostics-page"><a href="#" class="pg-back"><span aria-hidden="true">${I('ArrowLeft',18)}</span><span>${t('about.back')}</span></a><div class="dg-head">${h1}<div data-test="diagnostics-download"><button type="button" class="btn btn-primary dg-download-btn" ${busy?'aria-disabled="true" aria-busy="true"':'aria-busy="false"'}>${busy?spin()+t('bugReport.downloading'):I('Download',18)+t('diagnostics.downloadBundle')}</button></div></div>
<section class="dg-section" data-test="diagnostics-server" aria-labelledby="dg-server-title"><h2 id="dg-server-title" class="ui-h2">${t('diagnostics.serverInfo')}</h2><dl class="ui-card dg-kv">${row(t('diagnostics.version'),'1.5.0',1)}${row(t('diagnostics.python'),'3.11.9',1)}${row(t('diagnostics.platform'),plat,1)}${row(t('diagnostics.discovery'),badge('success','Check',t('common.enabled')))}${row(t('diagnostics.logLevel'),'INFO',1)}${row(t('diagnostics.manualIPs'),'2')}</dl></section>
<section class="dg-section" data-test="diagnostics-db" aria-labelledby="dg-db-title"><h2 id="dg-db-title" class="ui-h2">${t('diagnostics.database')}</h2><dl class="ui-card dg-kv">${row(t('diagnostics.devicesCount'),String(n))}${row(t('diagnostics.presetsCount'),String(n*6))}</dl></section>
<section class="dg-section" data-test="diagnostics-devices" aria-labelledby="dg-devices-title"><h2 id="dg-devices-title" class="ui-h2">${t('diagnostics.devices')}</h2>${devHtml}</section></div>`}

/* ---------- About ---------- */
const FN=['Anna','Bernd','Carla','Dieter','Eva','Frank','Gerda','Hans','Ines','Jörg','Katja','Lars','Mia','Nico','Olga','Paul','Rita','Sven','Tanja','Uwe','Vera','Walter','Yvonne','Zoran'];
const LN=['Müller','Schmidt','Schneider','Fischer','Weber','Meyer','Wagner','Becker','Hoffmann','Schäfer','Koch','Richter','Klein','Wolf','Neumann','Schwarz','Zimmermann','Braun'];
function supporters(n){let x=7;const r=()=>(x=(x*1103515245+12345)&0x7fffffff)/0x7fffffff;const out=[];
 for(let i=0;i<n;i++){let name=FN[Math.floor(r()*FN.length)]+' '+LN[Math.floor(r()*LN.length)];
  if(i%23===5)name='Maximilian-Alexander Freiherr von Hohenzollern-Sigmaringen-Wartenberg zu Oberndorf';
  else if(i%31===7)name='https://github.com/a-very-long-github-handle-without-any-breaks-in-it-'+i;
  else if(i%17===3)name=name+'@example.org';
  else if(i%41===9)name='@SupporterWithoutAnySpacesAtAll'+i;
  const monthly=r()<.15,amount=Math.round((r()<.1?60+r()*140:5+r()*40));out.push({name,amount,monthlyAmount:monthly?5+Math.round(r()*15):0})}
 return out.sort((a,b)=>(b.amount+b.monthlyAmount)-(a.amount+a.monthlyAmount))}
const cleanName=n=>{if(n.startsWith('https://github.com/'))return '@'+n.replace('https://github.com/','');const a=n.indexOf('@');return a>0?n.slice(0,a).trim():n};
const fontSize=(s,m)=>Math.floor(12+(32-12)*((s.amount+s.monthlyAmount)/m));
const lumG=([r,g,b])=>{const c=v=>v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4);return .2126*c(r)+.7152*c(g)+.0722*c(b)};
const h2rG=(h,s,l)=>{const a=s*Math.min(l,1-l),f=n=>{const k=(n+h/30)%12;return l-a*Math.max(-1,Math.min(k-3,9-k,1))};return[f(0),f(8),f(4)]};
const grad=(i,n)=>{const h=i/n*360,s=85+(i%4)*5;let l=58+(i%2)*4;while(l<90&&(lumG(h2rG(h,s/100,l/100))+.05)/(lumG([36/255,36/255,36/255])+.05)<4.8)l++;return `hsl(${h.toFixed(1)}, ${s}%, ${l}%)`}
function aboutHtml(){
 const ver=P('ver','ok'),up=P('up','available'),sup=+P('sup',200),bt=P('bt','0')==='1';
 const sl=sup?supporters(sup):[],mx=Math.max(...sl.map(s=>s.amount+s.monthlyAmount),1);
 const st=(cls,ic,body)=>`<div class="wz-status${cls} ab-status"><span class="wz-icon" aria-hidden="true">${ic}</span>${body}</div>`;
 let upd='';
 if(up==='checking')upd=`<div class="wz-status ab-status"><span class="wz-icon">${spin()}</span><div class="wz-status-body"><p>${t('about.checkingUpdates')}</p></div></div>`;
 else if(up==='available')upd=st('',I('Sparkles',22),`<div class="wz-status-body ab-update-body"><p>${t('about.updateAvailable',{version:'1.6.0'})}</p><a href="#" class="btn btn-primary btn-sm">${t('about.viewRelease')}${NT()}</a></div>`);
 else if(up==='uptodate')upd=st(' wz-status--success',I('CircleCheck',22),`<div class="wz-status-body"><p>${t('about.upToDate')}</p></div>`);
 else upd=st('',I('Wrench',22),`<div class="wz-status-body"><p>${t('about.devBuild')}</p></div>`);
 const lk=(ic,lbl,ext,cls)=>`<li><a href="#" class="ab-link${cls||''}"><span class="ab-link-icon" aria-hidden="true">${I(ic,22)}</span><span class="ab-link-label">${lbl}</span>${ext?NT():`<span class="ab-ext" aria-hidden="true">${I('ChevronRight',18)}</span>`}</a></li>`;
 return `<div class="ab"><header class="ab-header"><div class="ab-logo" style="display:flex;align-items:center;justify-content:center;background:#2a2a2a;border-radius:20px;color:#8ab8f0" aria-hidden="true">${I('Music',44)}</div><h1 class="ab-title">OpenCloudTouch</h1><div class="ab-version-slot">${ver==='loading'?'<span class="ui-skeleton" style="width:60px;height:24px;border-radius:20px"></span>':ver==='ok'?'<span class="ui-badge ui-badge--info ui-badge--large">v1.5.0</span>':''}</div>${bt?`<p class="ui-small ab-build-time">${t('about.buildTime',{time:'12.10.2026, 08:15:42'})}</p>`:''}</header>
<div class="ab-update" aria-live="polite">${upd}</div>
${sl.length?`<section class="ab-supporters" aria-labelledby="ab-supporters-title"><h2 id="ab-supporters-title" class="ui-h2" aria-label="${t('about.supportersLabel')}">Supp<span class="ab-heart" aria-hidden="true">${I('Heart',22)}</span>rters</h2><p class="ui-small ab-thanks">Danke, dass ihr OpenCloudTouch am Laufen haltet.</p><ul class="ui-card ab-cloud">${sl.map((s,i)=>{const m=s.monthlyAmount>0;return `<li class="ab-name${m?' ab-name--monthly':''}" style="font-size:${fontSize(s,mx)}px;${m?'':'color:'+grad(i,sl.length)+';'}--i:${Math.min(i,40)}">${esc(cleanName(s.name))}${m?` <span class="visually-hidden">${t('about.monthlySupporter')}</span>`:''}</li>`}).join('')}</ul></section>`:''}
<nav class="ab-links" aria-label="${t('about.linksLabel')}"><ul>${lk('Github',t('about.github'),1)}${lk('Bug',t('about.reportBug'),1)}${lk('Wrench',t('about.diagnostics'),0)}${lk('FileText',t('about.licenses'),0)}${lk('Coffee',t('about.support'),1,' ab-link--support')}</ul></nav></div>`}

/* ---------- Licenses ---------- */
const DEPS={frontend:[['React','18.2.0','MIT'],['React Router','6.20.0','MIT'],['Framer Motion','10.16.16','MIT']],backend:[['FastAPI','0.100+','MIT'],['uvicorn','latest','BSD-3-Clause'],['httpx','latest','BSD-3-Clause'],['aiosqlite','latest','MIT'],['pydantic','2.0+','MIT'],['libsoundtouch','latest','Apache-2.0']],build:[['Vite','5.0.8','MIT'],['pytest','latest','MIT'],['Docker','latest','Apache-2.0']]};
function licHtml(){
 const grp=(k)=>`<section class="lic-group" aria-labelledby="lic-g-${k}"><h2 id="lic-g-${k}" class="ui-h2">${t('about.licensesGroup.'+k)}</h2><ul class="ui-card lic-list">${DEPS[k].map(d=>`<li class="lic-item"><a class="lic-name" href="#" aria-label="${esc(t('about.libraryWebsite',{name:d[0]}))} ${t('about.externalLink')}"><span>${esc(d[0])}</span><span class="lic-ext" aria-hidden="true">${I('ExternalLink',14)}</span></a><span class="lic-version"><span class="lic-k">${t('about.licensesVersion')}</span> <span class="ui-mono">${d[1]}</span></span><span class="ui-badge lic-badge">${d[2]}</span></li>`).join('')}</ul></section>`;
 const tr=k=>t(k).replace(/<0>(.*?)<\/0>/g,(_,x)=>k.endsWith('2')?`<a class="lic-link" href="#">${x}</a>`:`<strong>${x}</strong>`);
 return `<div class="lic"><a href="#" class="pg-back"><span aria-hidden="true">${I('ArrowLeft',18)}</span><span>${t('about.back')}</span></a><header class="lic-header"><h1 class="ui-h1">${t('about.licensesTitle')}</h1><p class="lic-text">${t('about.licensesDescription')}</p></header>${grp('frontend')}${grp('backend')}${grp('build')}
<section class="ui-card lic-note" aria-labelledby="lic-compliance-title"><h2 id="lic-compliance-title" class="ui-h3">${t('about.licenseCompliance')}</h2><p class="lic-text">${t('about.licenseComplianceText')}</p><p class="lic-text"><strong>${t('about.licenseProject')}:</strong> <a class="lic-link" href="#">${t('about.licenseApache')}<span class="visually-hidden"> ${t('about.externalLink')}</span></a></p></section>
<section class="wz-status wz-status--warning lic-trademark" aria-labelledby="lic-trademark-title"><span class="wz-icon" aria-hidden="true">${I('Alert',22)}</span><div class="wz-status-body"><h2 id="lic-trademark-title" class="ui-h3">${t('about.trademarkTitle')}</h2><p>${tr('about.trademarkText1')}</p><p>${tr('about.trademarkText2')}</p></div></section>
<section class="lic-note lic-attribution" aria-labelledby="lic-about-title"><h2 id="lic-about-title" class="ui-h3">${t('about.sectionTitle')}</h2><p class="lic-text">${t('about.appDescription')}</p></section></div>`}

function render(){
 const root=document.getElementById('root');
 const act={settings:'settings',diag:'about',about:'about',licenses:'about'}[PG];
 const inner={settings:settingsHtml,diag:diagHtml,about:aboutHtml,licenses:licHtml}[PG]();
 const tk=P('toast','');
 const tt={scan:['success',t('settings.discovery.devicesFound_other',{count:3})],dev:['success',t('settings.manualIps.deviceAdded',{name:'Küche',ip:'192.168.1.22'})],level:['success',t('settings.logging.levelChanged',{level:'DEBUG'})],lerr:['error',t('settings.logging.levelError')],dgok:['success',t('bugReport.diagnosticsSuccess')],dgerr:['error',t('bugReport.diagnosticsFailed',{error:'HTTP 500'})]}[tk];
 root.innerHTML=shell(inner,act,false)+(tt?toast(tt[0],tt[1]):'');
}

/* ---------- audit ---------- */
const pc=c=>{const m=c.match(/[\d.]+/g).map(Number);return{r:m[0],g:m[1],b:m[2],a:m[3]==null?1:m[3]}};
const over=(f,b)=>({r:f.r*f.a+b.r*(1-f.a),g:f.g*f.a+b.g*(1-f.a),b:f.b*f.a+b.b*(1-f.a),a:1});
function bgOf(el){const ch=[];for(let e=el;e;e=e.parentElement){const c=pc(getComputedStyle(e).backgroundColor);if(c.a>0)ch.push(c);if(c.a>=1)break}let b={r:26,g:26,b:26,a:1};if(ch.length&&ch[ch.length-1].a>=1)b=ch.pop();ch.reverse().forEach(c=>b=over(c,b));return b}
const lum=c=>{const f=v=>{v/=255;return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4)};return .2126*f(c.r)+.7152*f(c.g)+.0722*f(c.b)};
function audit(){
 const vw=document.documentElement.clientWidth,R='#root',bad=[];
 const vis=e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0};
 const clipped=e=>{const r=e.getBoundingClientRect();for(let p=e.parentElement;p&&p.id!=='root';p=p.parentElement){const o=getComputedStyle(p).overflowY;if(/(auto|scroll|hidden|clip)/.test(o)&&p.scrollHeight>p.clientHeight+1){const q=p.getBoundingClientRect();if(r.top<q.top-1||r.bottom>q.bottom+1)return true}}return false};
 document.querySelectorAll(R+' *').forEach(el=>{if(el.closest('.np-marquee,.es-help ul,.dne-text-wrap'))return;const r=el.getBoundingClientRect();if(r.width&&(r.right>vw+1||r.left<-1)&&!el.closest('.ds-viewport,.dlg'))bad.push(el.className||el.tagName)});
 const small=[...document.querySelectorAll(R+' button,'+R+' a[href],'+R+' summary,'+R+' [role=slider],'+R+' [role=option],'+R+' input:not([type=hidden]),'+R+' select,'+R+' textarea')].filter(e=>{if(e.closest('.visually-hidden')||e.matches('.nav-label *'))return false;const r=e.getBoundingClientRect();if(!r.width||!r.height)return false;if(e.matches('.ui-toggle input'))return false;if(getComputedStyle(e).position==='absolute'&&r.width<=1)return false;if(clipped(e))return false;return r.height<43.5||r.width<(e.matches('.ds-dot')?23.5:43.5)}).map(e=>e.className||e.tagName);
 const ov=[],els=[...document.querySelectorAll(R+' button,'+R+' h1,'+R+' h2,'+R+' h3,'+R+' p,'+R+' li,'+R+' .pb-name,'+R+' .rs-name,'+R+' .dne-text-wrap')].filter(vis);
 for(let i=0;i<els.length;i++)for(let j=i+1;j<els.length;j++){const a=els[i],b=els[j];if(a.contains(b)||b.contains(a))continue;if(a.closest('dialog')!==b.closest('dialog'))continue;if(a.closest('.lang-dropdown')||b.closest('.lang-dropdown')||clipped(a)||clipped(b))continue;const A=a.getBoundingClientRect(),B=b.getBoundingClientRect();const w=Math.min(A.right,B.right)-Math.max(A.left,B.left),h=Math.min(A.bottom,B.bottom)-Math.max(A.top,B.top);if(w>2&&h>2)ov.push((a.className||a.tagName)+' x '+(b.className||b.tagName))}
 const scr=[...document.querySelectorAll(R+' *')].filter(e=>{if(!vis(e)||e.matches('main,body,.app-main,.dlg,.dlg-overlay'))return false;const cs=getComputedStyle(e);return /(auto|scroll)/.test(cs.overflowY)&&e.scrollHeight>e.clientHeight+1&&e.tabIndex<0&&!e.querySelector('button,a[href],input,textarea,select,[tabindex]')}).map(e=>e.className);
 const lo=[];
 document.querySelectorAll(R+' *').forEach(e=>{if(!vis(e)||e.disabled||e.closest('[disabled],svg,.pb-avatar,.rs-avatar,[aria-hidden=true]'))return;const own=[...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim());if(!own)return;const cs=getComputedStyle(e);const fg=pc(cs.color);const bg=bgOf(e);const f=over({...fg,a:fg.a*parseFloat(cs.opacity||1)},bg);const L1=lum(f),L2=lum(bg),ratio=(Math.max(L1,L2)+.05)/(Math.min(L1,L2)+.05);const fs=parseFloat(cs.fontSize),big=fs>=24||(fs>=18.66&&+cs.fontWeight>=700);if(ratio<(big?3:4.5)-.02)lo.push((e.className||e.tagName)+' '+ratio.toFixed(2))});
 const ok=!(document.documentElement.scrollWidth>vw+1)&&!bad.length&&!small.length&&!ov.length&&!scr.length&&!lo.length;
 const a=document.getElementById('audit');a.style.background=ok?'#1b5e20':'#b71c1c';a.style.color='#fff';
 const msg=ok?`✓ ${vw}px: kein Overflow, keine Überlappung, Ziele ≥44px, Kontrast ≥4,5:1, Scroll-Bereiche fokussierbar`:`✗ ${vw}px: ${document.documentElement.scrollWidth>vw+1?'Scroll. ':''}${bad.slice(0,2).join(', ')}${small.length?' | <44px: '+small.slice(0,2).join(', '):''}${ov.length?' | Überlappung: '+ov.slice(0,2).join(', '):''}${scr.length?' | Scroll ohne tabindex: '+scr.slice(0,2).join(', '):''}${lo.length?' | Kontrast: '+lo.slice(0,3).join(', '):''}`;
 a.textContent=msg;parent.postMessage({oct:'audit',ok,msg,v:P('v','after'),diag:DIAG},'*');
}


const merge=(a,b)=>{for(const k in b){if(b[k]&&typeof b[k]==='object'&&!Array.isArray(b[k])){a[k]=merge(a[k]&&typeof a[k]==='object'?a[k]:{},b[k])}else a[k]=b[k]}return a};
Promise.all([fetch('de-texts.json').then(r=>r.json()),fetch('i18n-stage7-additions.json').then(r=>r.json())]).then(([a,b])=>{TX=merge(a,b.de);render();requestAnimationFrame(()=>setTimeout(audit,500))}).catch(e=>{document.getElementById('root').textContent='Fehler: '+e});
