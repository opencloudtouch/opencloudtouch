/* Stage 6b prototype pages: before = committed CSS (app6b/before), after = new CSS (app6b). Markup mirrors the TSX. */
Object.assign(PA,{
Link:'<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
Unlink:'<path d="m18.84 12.25 1.72-1.71h-.02a5.004 5.004 0 0 0-.12-7.07 5.006 5.006 0 0 0-6.95 0l-1.72 1.71"/><path d="m5.17 11.75-1.71 1.71a5.004 5.004 0 0 0 .12 7.07 5.006 5.006 0 0 0 6.95 0l1.71-1.71"/>',
Star:'<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>'});
const PG=P('page','presets'),B=P('v','after')==='before';
const tt=(k,f,v)=>{const x=t(k,v);return x===k?f:x};
const NAMES={short:'Bad',std:'Wohnzimmer',mid:'Schlafzimmer Obergeschoss',long:'Wohnzimmer Regal Lautsprecher Anbau Neu1'};
const OTH=['Küche','Schlafzimmer','Büro','Bad DG','Terrasse','Keller','Flur','Gästezimmer','Garage','Dachboden','Werkstatt'];
const dn0=i=>i===0?NAMES[P('name','std')]:(OTH[(i-1)%OTH.length]+(i>OTH.length?' '+i:''));
let DEVN=+P('dev',5);const DEVL=Array.from({length:DEVN},(_,i)=>dn0(i));const dn=i=>DEVL[i];
const OFFN=new Set((P('off','2').split(',').filter(Boolean)).map(k=>DEVL[+k]).filter(Boolean));const isOff=i=>OFFN.has(DEVL[i]);let TOASTMSG='';
let DIAG='';
const artSrc='data:image/svg+xml;utf8,'+encodeURIComponent(ART);

/* ---------- dots ---------- */
const FULLW=44,MINW=24;
function dotLayout(n,w){if(!w||n*FULLW<=w)return{d:'full',vis:n,pitch:FULLW};if(n*MINW<=w)return{d:'dense',vis:n,pitch:Math.floor(w/n*10)/10};const vis=Math.max(3,Math.floor(w/MINW));return{d:'window',vis,pitch:Math.floor(w/vis*10)/10}}
function dotsHtml(n,i){
 const L=B?{d:'old',vis:n,pitch:44}:dotLayout(n,S.dw||0);
 let start=0;if(L.d==='window')start=Math.min(Math.max(i-Math.floor(L.vis/2),0),n-L.vis);
 let h='';for(let k=start;k<start+L.vis;k++){const edge=L.d==='window'&&((k===start&&start>0)||(k===start+L.vis-1&&start+L.vis<n));
  h+=`<button class="ds-dot${k===i?' ds-dot--active':''}${edge?' ds-dot--edge':''}" ${k===i?'aria-current="true"':''} aria-label="${t('a11y.switchToDevice',{name:dn(k)})}" title="${esc(dn(k))}" data-act="dot" data-i="${k}"></button>`}
 return `<div class="ds-dots${B?'':' ds-dots--'+L.d}" role="group" aria-label="${t('a11y.deviceSelection')}" style="--ds-pitch:${L.pitch}px">${h}${L.d==='window'?`<span class="visually-hidden" role="status">${tt('a11y.deviceCounter','Gerät '+(i+1)+' von '+n,{current:i+1,total:n})}</span>`:''}</div>`}
function swiperHtml(n,i,card){
 const pv=`<button class="ds-arrow ds-arrow--prev" ${i===0?'disabled':''} aria-label="${t('player.prevDevice')}" data-act="prev">${I('ChevronLeft',24)}</button>`,nx=`<button class="ds-arrow ds-arrow--next" ${i===n-1?'disabled':''} aria-label="${t('player.nextDevice')}" data-act="next">${I('ChevronRight',24)}</button>`;
 const at=(!B&&i>0?' data-prev':'')+(!B&&i<n-1?' data-next':'');
 const cardH=B?`<div class="ds-card">${card(i)}</div>`:`<div class="ds-card"><div class="ds-card-shell" data-state="current">${card(i)}</div></div>`;
 const top=ST?`<div class="ds-bar">${pv}${dotsHtml(n,i)}<span class="ds-bar-name" aria-hidden="true">${esc(dn(i))} · ${i+1}/${n}</span>${nx}</div>`:`${pv}${nx}`;
 return `<div class="ds" data-test="device-swiper"${at}>${top}<div class="ds-viewport">${cardH}</div>${ST?'':dotsHtml(n,i)}</div>`}

/* ---------- name + now playing ---------- */
function nameHtml(n){const nm=P('nm','display');
 if(nm==='edit'||nm==='error')return `<div class="dne" data-test="device-name-editor"><h2 class="dne-heading"><span class="dne-field"><input class="ui-input dne-input" type="text" value="${esc(n)}" maxlength="30" aria-label="${t('deviceRename.inputLabel')}" ${nm==='error'?'aria-invalid="true" aria-describedby="device-name-error"':''}></span></h2>${nm==='error'?`<span id="device-name-error" class="ui-field-error dne-error" role="alert">${I('CircleX',16)}<span>${t('deviceRename.failed')}</span></span>`:''}</div>`;
 if(B)return nameBlock(n,'display');
 return `<h2 class="dne-heading"><button type="button" class="dne-btn" title="${t('deviceRename.clickToEdit')}" aria-label="${esc(n)} — ${t('deviceRename.clickToEdit')}" data-test="device-name"><span class="dne-text-wrap"><span class="dne-text">${esc(n)}</span></span><span class="dne-icon" aria-hidden="true">${I('Pencil',16)}</span></button></h2>`}
function fitNames(){document.querySelectorAll('.dne-text-wrap').forEach(w=>{const s=w.firstElementChild,x=s.scrollWidth-w.clientWidth;if(x>1){s.classList.add('dne-text--scrolling');s.style.setProperty('--marquee-distance','-'+Math.ceil(x)+'px');s.style.animationDuration=Math.max(6,x/10)+'s'}})}
const LONGT='Symphonie Nr. 9 in d-Moll, Op. 125 – IV. Presto – Allegro assai (Ode an die Freude)',LONGA='Berliner Philharmoniker, Herbert von Karajan, Wiener Singverein';
const mq=(c,x)=>`<div class="np-marquee ${c}" title="${esc(x)}"><span class="np-marquee-inner">${esc(x)}</span></div>`;
function npHtml(st,overlay=true){
 if(st==='none')return `<div class="np np--empty"><span class="np-empty-icon" aria-hidden="true">${I('Music',28)}</span><div class="np-placeholder">${t('player.noPlayback')}</div></div>`;
 const d={full:{st:'SWR3',tr:'Don’t Stop Believin’',ar:'Journey',src:1},notrack:{st:'SWR3',tr:'',ar:'',src:1},noartist:{st:'SWR3',tr:'Don’t Stop Believin’',ar:'',src:1},long:{st:'SWR3',tr:LONGT,ar:LONGA,src:1},late:{st:'',tr:'',ar:'',src:0}}[st]||{st:'SWR3',tr:'',ar:'',src:1};
 return `<div class="np"><div class="np-header">${d.src?`<div class="ui-source np-source radio" role="img" aria-label="${t('player.source.radio')}">${I('Radio',20)}</div>`:''}<div class="np-station">${esc(d.st||t('player.noStation'))}</div></div><div class="np-art"><img alt="" src="${artSrc}">${overlay?`<button class="np-play-overlay" aria-label="${t('player.play')}">${I('Play',28)}</button>`:''}</div><div class="np-info">${d.tr?mq('np-track',d.tr):''}${d.ar?mq('np-artist',d.ar):''}</div></div>`}
function marquee2(){document.querySelectorAll('.np-marquee').forEach(w=>{const s=w.firstElementChild;if(s.scrollWidth>w.clientWidth+1){const d=s.scrollWidth-w.clientWidth;s.classList.add('np-marquee-inner--scrolling');s.style.setProperty('--marquee-distance','-'+d+'px');s.style.animationDuration=Math.max(6,d/10)+'s'}})}
const lcPh=loading=>`<div class="np lc-ph${loading?'':' lc-ph--idle'}" ${loading?`role="status" aria-label="${t('common.loading')}"`:''}><div class="np-header lc-ph-head">${loading?'<span class="ui-skeleton lc-ph-tile"></span><span class="ui-skeleton lc-ph-line lc-ph-station"></span>':''}</div><div class="np-art lc-ph-art">${loading?'<span class="ui-skeleton lc-ph-fill"></span>':`<div class="lc-ph-empty"><span aria-hidden="true">${I('Music',32)}</span><span>${t('player.noPlayback')}</span></div>`}</div><div class="np-info lc-ph-info">${loading?'<span class="ui-skeleton lc-ph-line lc-ph-track"></span><span class="ui-skeleton lc-ph-line lc-ph-artist"></span>':''}</div></div>`;

/* ---------- pages ---------- */
function rpHead(i){const n=dn(i);return `<div class="rp-card-head"><button type="button" class="rp-power rp-power--on" aria-label="${t('player.powerButton')}" aria-pressed="true" title="${t('player.powerButton')}">${I('Power',22)}</button><div class="rp-device-info">${nameHtml(n)}<span class="rp-device-model" data-test="device-model">SoundTouch 10</span><span class="rp-device-ip" data-test="device-ip">192.168.178.${142+i}</span></div><div class="rp-card-badge">${setupBadge(isOff(i)?'offline':(i%3===0?'configured':'unconfigured'))}</div></div>`}
const rmFoot=i=>{const o=isOff(i);return `<div class="dm-foot"><button type="button" class="btn ${o?'btn-danger-outline':'btn-ghost dm-quiet'} dm-remove" data-act="rm" data-test="device-remove">${I('Trash',18)}<span>${tt('presets.removeDevice','Gerät entfernen')}</span></button></div>`};
const offBanner=i=>`<div class="wz-status wz-status--warning dob" role="status">${WI('WifiOff',22)}<div class="wz-status-body"><p><strong>${t('errors.offlineTitle')}</strong></p><p>${esc(t('errors.offlineDetail',{name:dn(i)}))}</p></div></div>`;
function rpCard(i){const o=isOff(i);return `<div class="rp-card" data-test="device-card">${rpHead(i)}${o?offBanner(i):npHtml(P('np','full'))+volume(false,21)}${rmFoot(i)}</div>`}
const PRN=['SWR3',null,'Antenne Bayern',null,null,'NDR 2'];
function presetsPage(){const i=Math.min(S.i,DEVN-1);return `<div class="rp"><h1 class="rp-title">Radio Presets</h1><div class="rp-device">${swiperHtml(DEVN,i,rpCard)}</div><section class="rp-presets" aria-labelledby="rp-presets-title"><div class="ui-section-header"><h2 id="rp-presets-title" class="ui-h2">Gespeicherte Sender</h2><button class="btn btn-secondary rp-sync">${I('RefreshCw',18)} Vom Gerät laden</button></div><div class="rp-grid">${PRN.map((n,k)=>preset(k+1,n,k===0&&!isOff(i),isOff(i))).join('')}</div></section><div class="wz-status rp-info">${WI('Info',24)}<div class="wz-status-body"><h2 class="rp-info-title">Preset Hinweise</h2><ul class="rp-info-list"><li>Klicke auf ein leeres Preset um einen Sender zuzuweisen</li><li>Klicke auf einen belegten Sender um ihn zu ändern oder zu löschen</li></ul></div></div></div>`}
/* ---------- 9: sources + transport keys ---------- */
const SRC9={radio:['Radio','radio','Radio','SWR3','Don’t Stop Believin’','Journey'],bt:['Bluetooth','bluetooth','Bluetooth','iPhone von Max','Blinding Lights','The Weeknd'],airplay:['Airplay','airplay','AirPlay','MacBook Pro','Midnight City','M83'],dlna:['Speaker','dlna','DLNA','Fritz!NAS','Africa','Toto'],spotify:['Music','streaming','Spotify','','Bohemian Rhapsody – Remastered 2011','Queen'],aux:['Headphones','aux','AUX','','',''],tv:['Tv','tv','TV / HDMI','','','']};
const TRANS={radio:[0,1,0],bt:[1,1,1],airplay:[1,1,1],dlna:[1,1,1],spotify:[1,1,1],aux:[0,0,0],tv:[0,0,0]};   /* prev, play/pause, next available */
function npSrc(key){
 const d=SRC9[key],v=P('np9','full');
 const sv={full:['',''],notrack:['__',''],noartist:['','__'],long:[LONGT,LONGA]}[v]||['',''];
 let tr=d[4],ar=d[5],st=d[3];
 if(v==='notrack'){tr='';ar='';}else if(v==='noartist'){ar='';}else if(v==='long'&&tr){tr=LONGT;ar=LONGA;st=st?st+' '+LONGA:st}
 if(key==='radio')return npHtml(v==='full'?'full':v,false);
 const head=st?d[2]+' · '+st:d[2];
 return `<div class="np"><div class="np-header"><div class="ui-source np-source ${d[1]}" role="img" aria-label="${d[2]}">${I(d[0],20)}</div><div class="np-station">${esc(head)}</div></div><div class="np-art"><img alt="" src="${artSrc}"></div><div class="np-info">${tr?mq('np-track',tr):''}${ar?mq('np-artist',ar):''}</div></div>`}
function transport(key,playing,busy,usable){
 const av=TRANS[key]||[0,0,0],k=(id,cls,ic,label,on,sz)=>{const ld=busy===id;return `<button type="button" class="lc-key${cls}" data-test="lc-${id}" aria-label="${label}" ${ld?'disabled aria-busy="true"':(!on||!usable?'disabled':'')}>${ld?'<span class="ui-spin">'+I('Loader',sz||24)+'</span>':I(ic,sz||24)}</button>`};
 return `<div class="lc-transport" role="group" aria-label="${t('player.playbackTitle')}" data-test="lc-playback">${k('prev','','SkipBack',t('player.prevTrack'),av[0])}${k('play',' lc-key--primary',playing?'Pause':'Play',playing?t('player.pause'):t('player.play'),av[1],32)}${k('next','','SkipForward',t('player.nextTrack'),av[2])}</div>`}
function lcCard(i){const zone=P('zone','0')==='1',src=P('src','bt'),stby=P('st','')==='standby',nd=P('st','')==='nodata',busy=P('k',''),playing=P('play','1')==='1'&&!stby&&!nd,usable=!stby&&!nd;
 const np=stby||nd?lcPh(false):npSrc(src);
 return `<div class="lc-card"><div class="lc-head${zone?' lc-head--zone':''}"><button type="button" class="lc-power ${stby?'lc-power--off':'lc-power--on'}" aria-label="${t('player.powerButton')}" aria-pressed="${!stby}" title="${t('player.powerButton')}">${I('Power',22)}</button><div class="lc-info">${nameHtml(dn(i))}<span class="lc-model">SoundTouch 30</span></div><div class="lc-end">${zone?`<button type="button" class="lc-zone" title="Zone: Master">${I('Link',16)}<span>${t('multiroom.masterBadge')}</span></button>`:''}${setupBadge(isOff(i)?'offline':'configured')}</div></div>${isOff(i)?offBanner(i):`<div class="lc-np">${np}</div>${transport(src,playing,busy,usable)}<div class="lc-volume">${volume(false,62)}</div>`}${rmFoot(i)}</div>`}
function localPage(){const i=Math.min(S.i,DEVN-1);return `<div class="lc"><h1 class="ui-h1 lc-title">${t('player.localControl')}</h1><div class="lc-device">${swiperHtml(DEVN,i,lcCard)}</div></div>`}

function lcHead(i,zone){return `<div class="lc-head${zone?' lc-head--zone':''}"><button type="button" class="lc-power lc-power--on" aria-label="${t('player.powerButton')}" aria-pressed="true">${I('Power',22)}</button><div class="lc-info">${nameHtml(dn(i))}<span class="lc-model">SoundTouch 30</span></div><div class="lc-end">${zone?`<button type="button" class="lc-zone" title="Zone: Master">${I('Link',16)}<span>${t('multiroom.masterBadge')}</span></button>`:''}${setupBadge('configured')}</div></div>`}
function headsPage(){const W=[288,340,376,480,560];
 return `<div class="pg"><h1 class="ui-h1">Kopfzeile: gleiche Anordnung bei jeder Kartenbreite</h1><p class="ui-small">Breiten der echten Karten: 288 px = Phone 320; 340 px = Presets bei 1280; 376 = Presets bei 1024; 480 = Tablet; 560 px = Lokale Steuerung bei 1280. Namensbreite: Name oben, Modell und IP darunter, immer.</p>`+
 W.map(w=>`<div class="col"><h2 class="sec">Karte ${w} px</h2><div class="row" style="align-items:flex-start"><div class="rp-card" style="width:${w}px;max-width:100%">${rpHead(0)}</div><div class="lc-card" style="width:${w}px;max-width:100%">${lcHead(0,true)}</div></div></div>`).join('')+`</div>`}
/* ---------- now playing: reserved height ---------- */
function npPage(){
 const pairs=[['Leer (nur Sender) → Titel und Interpret','notrack','full'],['Nur Titel → Titel und Interpret','noartist','full'],['Header spät (kein Sender, keine Quelle) → voll','late','full'],['Lange Titel (Laufschrift)','long','long']];
 const card=h=>`<div class="ui-card np-demo" style="width:min(288px,100%)">${h}</div>`;
 return `<div class="pg"><h1 class="ui-h1">NowPlaying: reservierte Höhe</h1><p class="ui-small">Gemessen mit dem geladenen CSS (Vorher / Nachher), Kartenbreite 288 px. Sprung = Höhe voll minus Höhe leer.</p>`+
 pairs.map((p,k)=>`<div class="col"><h2 class="sec">${p[0]}</h2><div class="row" style="align-items:flex-start">${card(npHtml(p[1],false))}${card(npHtml(p[2],false))}</div><p class="ui-small npm" data-k="${k}"></p></div>`).join('')+
 `<div class="col"><h2 class="sec">Kompakte Varianten (Lokale Steuerung, Zonen-Karte)</h2><div class="row" style="align-items:flex-start">${card(lcPh(true))}${card(lcPh(false))}${card(npHtml('full',false))}</div><div class="row" style="align-items:flex-start"><div class="ui-card zn" style="width:min(340px,100%)"><div class="zn-np">${npHtml('notrack',false)}</div></div><div class="ui-card zn" style="width:min(340px,100%)"><div class="zn-np">${npHtml('full',false)}</div></div></div><p class="ui-small npc"></p></div></div>`}
function measureNp(){
 const cards=[...document.querySelectorAll('.np-demo')];let out=[];
 document.querySelectorAll('.npm').forEach((p,k)=>{const a=cards[k*2].querySelector('.np').offsetHeight,b=cards[k*2+1].querySelector('.np').offsetHeight;p.textContent=`Höhe leer: ${a} px · Höhe voll: ${b} px · Sprung: ${b-a} px`;out.push(`${k+1}: ${b-a}px`)});
 const c=cards.slice(8).map(x=>x.querySelector('.np').offsetHeight);const z=[...document.querySelectorAll('.zn-np .np')].map(x=>x.offsetHeight);
 const pc=document.querySelector('.npc');if(pc)pc.textContent=`Platzhalter lädt: ${c[0]} px · Platzhalter leer: ${c[1]} px · echte Karte: ${c[2]} px · Zonen-Zeile (ohne Titel / voll): ${z[0]} / ${z[1]} px`;
 DIAG='Sprung (leer→voll): '+out.join(' · ')+(c.length?` · Platzhalter ${c[0]}/${c[1]} vs. echt ${c[2]} px`:'')}

/* ---------- station search ---------- */
const STS=[['SWR3','Deutschland'],['Deutschlandfunk','Deutschland'],['Antenne Bayern – Das beste Programm Bayerns, rund um die Uhr','Deutschland'],['1LIVE','Deutschland'],['Bayern 3','Deutschland'],['NDR 2','Deutschland']];
const rsItems=n=>STS.slice(0,n).map(s=>`<button class="rs-item"><div class="rs-logo"><span class="rs-avatar" style="display:flex;background-color:hsl(${hue(s[0])} 45% 32%)">${ini(s[0])}</span></div><div class="rs-info"><div class="rs-name">${esc(s[0])}</div><div class="rs-country">${s[1]}</div></div><span class="rs-chevron" aria-hidden="true">${I('ChevronRight',20)}</span></button>`).join('');
const OVR={};const SV=()=>OVR.s||P('s','results');
function rsResults(s){
 let h='';
 if(s==='error')h=`<div class="wz-status wz-status--error" role="alert"><span class="wz-icon" aria-hidden="true">${I('CircleX',20)}</span><div class="wz-status-body"><p class="search-error">${tt('presets.searchFailed','Die Suche ist fehlgeschlagen.')}</p></div></div>`;
 else if(s==='loading')h=`<div class="rs-note" role="status"><span class="spinner-small rs-spinner" aria-hidden="true"></span>${tt('presets.searchLoading','Suche läuft…')}</div>`;
 else if(s==='empty')h=`<div class="rs-note" role="status">${tt('presets.searchEmpty','Keine Sender gefunden')}</div>`;
 else if(s==='hint')h=`<div class="rs-note rs-note--hint">${I('Search',20)}<span>${tt('presets.searchHint','Mindestens 2 Zeichen eingeben')}</span></div>`;
 else h=rsItems(6)+(s==='many'?`<button class="btn btn-secondary rs-more">${tt('presets.loadMore','Mehr laden')}</button>`:'');
 return `<div class="rs-results rs-scroll" tabindex="0" role="region" aria-label="${tt('presets.searchResults','Suchergebnisse')}">${h}</div>`}
function searchDialog(){
 const s=SV(),man=s.startsWith('manual'),ex=P('ex','0')==='1'||s==='manualfilled',inv=s==='manualinvalid',filled=s==='manualfilled';
 const q=(s==='hint'||man)?'':'swr';
 const title=tt('presets.searchTitle','Sender suchen'),close=`<button class="btn btn-ghost btn-icon dlg-close rs-close" aria-label="${tt('presets.searchClose','Schließen')}" title="${tt('presets.searchClose','Schließen')}">${I('X',22)}</button>`;
 const chip=(l,p,d)=>`<button class="ui-chip" aria-pressed="${p}" ${d?'disabled':''}>${l}</button>`;
 const typeL=k=>tt('presets.searchTypeLabel.'+k,{name:'Name',country:'Land',tag:'Tag'}[k]);
 const chips=`<div class="rs-chips"><div class="ui-chips" role="group" aria-label="${tt('presets.searchTypeGroup','Suchtyp')}">${chip(typeL('name'),B?!man:true,man)}${chip(typeL('country'),false,man)}${chip(typeL('tag'),false,man)}</div><div class="ui-chips" role="group" aria-label="${tt('presets.providerGroup','Anbieter')}">${chip('TuneIn',!man,false)}${chip('RadioBrowser',false,false)}${chip(tt('presets.manualStreamMode','Stream URL'),man,false)}</div></div>`;
 const urlV=filled?'https://stream.example.com/live.mp3':inv?'stream.example.com':'';
 const urlIn=`<input type="url" class="ui-input" placeholder="${tt('presets.manualStreamUrlPlaceholder','Stream-URL eingeben…')}" value="${urlV}" aria-label="${tt('presets.manualStreamUrlPlaceholder','Stream-URL')}" ${inv?'aria-invalid="true"':''}>`;
 const hint=`<div class="ui-field-hint">${tt('presets.manualStreamUrlHelp','Direkte http(s)-Adresse eines Streams')}</div>${inv?`<div class="ui-field-error">${I('CircleX',16)}<span>${tt('presets.manualInvalidUrl','Ungültige URL')}</span></div>`:''}`;
 const searchIn=`<input type="search" class="ui-input rs-search" placeholder="${tt('presets.searchPlaceholder.name','Sendername suchen…')}" aria-label="${title}" value="${q}">`;
 const manual=`<div class="rs-manual rs-scroll" tabindex="0" role="region" aria-label="${tt('presets.manualStreamMode','Stream URL')}">${B?`<div class="ui-field">${hint}</div>`:''}<div class="ui-field"><input type="text" class="ui-input" placeholder="${tt('presets.manualStationNamePlaceholder','Sendername')}" value="${filled?'Mein Sender':''}" aria-label="${tt('presets.manualStationNamePlaceholder','Sendername')}"><div class="ui-field-hint">${tt('presets.manualStationNameHelp','Wird als Name im Preset angezeigt')}</div></div><div class="ui-field"><input type="url" class="ui-input" placeholder="${tt('presets.manualFaviconPlaceholder','Logo-URL (optional)')}" aria-label="${tt('presets.manualFaviconPlaceholder','Logo-URL')}"><div class="ui-field-hint">${tt('presets.manualFaviconHelp','Optional: Bild-Adresse für das Logo')}</div></div><button class="btn btn-primary btn-block-phone rs-submit" ${filled?'':'disabled'}>${tt('presets.manualUseStation','Sender verwenden')}</button></div>`;
 const del=`<button class="btn btn-danger-outline rs-delete-btn" aria-label="${tt('presets.deletePreset','Preset löschen')}">${I('Trash',18)} ${tt('presets.deletePreset','Preset löschen')}</button>`;
 let inner;
 if(B)inner=`<div class="rs-head"><h2 id="rs-title" class="dlg-title">${title}</h2>${man?`<div class="rs-url-field">${urlIn}</div>`:searchIn}${close}</div>${man?manual:''}${chips}${ex?`<div class="rs-delete">${del}</div>`:''}${man?'':rsResults(s)}`;
 else inner=`<div class="rs-head"><h2 id="rs-title" class="dlg-title">${title}</h2>${close}</div>${chips}<div class="rs-field">${man?`<div class="rs-url-field">${urlIn}${hint}</div>`:searchIn}</div>${man?manual:rsResults(s)}${ex?`<div class="rs-foot">${del}</div>`:''}`;
 return dlg('lg','dialog','rs-title',null,inner)}
function searchPage(){return shell('<div class="pg"><h1 class="ui-h1">Radio Presets</h1></div>','presets',false)}
function measureSearch(){
 const top=()=>{const p=document.querySelector('.dlg-panel'),c=document.querySelector('.rs-chips');return p&&c?Math.round(c.getBoundingClientRect().top-p.getBoundingClientRect().top):-1};
 const res={};
 for(const s of ['results','manual','manualinvalid']){OVR.s=s;render(true);res[s]=top()}
 OVR.s=null;delete OVR.s;render(true);
 const ph=document.querySelector('.dlg-panel')?.getBoundingClientRect().height||0;const rs=document.querySelector('.rs-results,.rs-manual');
 const sc=rs?Math.round(rs.getBoundingClientRect().height):0;
 DIAG=`Chips-Oberkante: Anbieter ${res.results}px · Stream URL ${res.manual}px · URL ungültig ${res.manualinvalid}px (Sprung ${Math.max(res.results,res.manual)-Math.min(res.results,res.manual)}px) · Inhaltsbereich ${sc}px von ${Math.round(ph)}px`}

/* ---------- motion lab ---------- */
const MX={before:{old:[{opacity:[1,0],dur:200,ease:'ease-in-out'},{x:[0,-1000],dur:330,ease:'cubic-bezier(.3,.7,.4,1)'}],nw:[{opacity:[0,1],dur:200,delay:330,ease:'ease-in-out'},{x:[1000,0],dur:260,delay:330,ease:'cubic-bezier(.2,.9,.3,1)'}]},
 after:{old:[{opacity:[1,0],dur:130,ease:'linear'},{x:[0,-16],dur:130,ease:'cubic-bezier(.4,0,1,1)'}],nw:[{opacity:[0,1],dur:130,ease:'linear'},{x:[32,0],dur:190,ease:'cubic-bezier(.16,1,.3,1)'}]}};
function mkAnims(kind,oe,ne){const o=[],n=[];
 const go=(el,spec,arr)=>{const kf=[],so=spec.find(s=>s.opacity),sx=spec.find(s=>s.x);
  arr.push(el.animate({opacity:so.opacity},{duration:so.dur,delay:so.delay||0,easing:so.ease,fill:'both'}));
  arr.push(el.animate({transform:[`translateX(${sx.x[0]}px)`,`translateX(${sx.x[1]}px)`]},{duration:sx.dur,delay:sx.delay||0,easing:sx.ease,fill:'both'}))};
 go(oe,MX[kind].old,o);go(ne,MX[kind].nw,n);return[o,n]}
function sampleMotion(kind){const lab=document.getElementById('mlab'),oe=lab.querySelector('.mc-old'),ne=lab.querySelector('.mc-new');
 const [o,n]=mkAnims(kind,oe,ne);const rows=[];let minCov=1,gapFrom=null,gapTo=null,done=0;
 for(let t=0;t<=700;t++){[...o,...n].forEach(a=>{a.pause();a.currentTime=t});const oo=+getComputedStyle(oe).opacity,no=+getComputedStyle(ne).opacity,cov=1-(1-oo)*(1-no);
  if(cov<minCov)minCov=cov;if(cov<0.5){if(gapFrom==null)gapFrom=t;gapTo=t}
  if([0,30,60,90,120,150,190,250,330,400,530].includes(t))rows.push({t,o:oo,n:no,c:cov});
  if(no<0.999||Math.abs(+getComputedStyle(ne).transform.split(',')[4]||0)>0.5)done=t+1}
 [...o,...n].forEach(a=>a.cancel());return{rows,minCov,gapFrom,gapTo,done}}
function motionPage(){return `<div class="pg"><h1 class="ui-h1">Bewegung beim Gerätewechsel</h1><p class="ui-small">Vorher ist ein Modell nach Ihren Messwerten (mode="wait", Feder über 1000 px). Nachher ist die Spezifikation aus den Notes (popLayout, Überblendung). Die Tabellen sind echte Abtastungen (1-ms-Schritte) der abgespielten Animationen. „Deckung“ = Anteil der Fläche, der von mindestens einer Karte bedeckt wird.</p><div class="row"><button class="btn btn-secondary" data-act="mplay" data-m="before">Vorher abspielen</button><button class="btn btn-primary" data-act="mplay" data-m="after">Nachher abspielen</button></div><div class="mlab" id="mlab" aria-hidden="true"><div class="mc mc-old">Gerät A</div><div class="mc mc-new">Gerät B</div></div><div id="mtabs" class="col"></div></div>`}
function fillMotion(){const box=document.getElementById('mtabs');if(!box)return;let h='',sum='';
 for(const k of ['before','after']){const r=sampleMotion(k);k==='before'?(r.b=1):0;
  h+=`<h2 class="sec">${k==='before'?'Vorher (Modell)':'Nachher (Vorschlag)'}</h2><table class="mt"><thead><tr><th>ms</th><th>alt</th><th>neu</th><th>Deckung</th></tr></thead><tbody>${r.rows.map(x=>`<tr${x.c<0.5?' class="mt-bad"':''}><td>${x.t}</td><td>${x.o.toFixed(2)}</td><td>${x.n.toFixed(2)}</td><td>${Math.round(x.c*100)} %</td></tr>`).join('')}</tbody></table><p class="ui-small">${r.gapFrom!=null?`Deckung unter 50 % von ${r.gapFrom} bis ${r.gapTo} ms (${r.gapTo-r.gapFrom+1} ms). `:'Nie unter 50 % Deckung. '}Minimum: ${Math.round(r.minCov*100)} % · ruhig nach ${r.done} ms</p>`;
  sum+=`${k==='before'?'Vorher':'Nachher'}: min. Deckung ${Math.round(r.minCov*100)} %, ruhig nach ${r.done} ms. `;r.d=r.done;S['m_'+k]=r}
 const f=S.m_before.done,a=S.m_after.done;sum+=`Schneller um ${Math.round((1-a/f)*100)} %.`;box.innerHTML=h;DIAG=sum}
function playMotion(kind){const lab=document.getElementById('mlab'),oe=lab.querySelector('.mc-old'),ne=lab.querySelector('.mc-new');[oe,ne].forEach(e=>e.getAnimations().forEach(a=>a.cancel()));const [o,n]=mkAnims(kind,oe,ne);[...o,...n].forEach(a=>a.play());}

function confirmRm(){const i=S.i,o=isOff(i),n=dn(i);
 return dlg('sm','alertdialog','rm-title','rm-msg',`<div class="dlg-head"><h2 id="rm-title" class="dlg-title">${tt('presets.removeDeviceTitle','Gerät entfernen?')}</h2></div><div class="dlg-body"><p class="dm-who"><span aria-hidden="true">${I('Speaker',20)}</span><span class="dm-who-name">${esc(n)}</span><span class="ui-mono dm-who-ip">192.168.178.${142+i}</span></p><p id="rm-msg" class="dlg-text">${esc(t(o?'presets.removeDeviceOffline':'presets.removeDeviceOnline',{name:n}))}</p></div><div class="dlg-actions"><button class="btn btn-secondary" data-act="rmno" autofocus>${t('common.cancel')}</button><button class="btn btn-danger" data-act="rmok" data-testid="confirm-dialog-confirm">${tt('presets.removeDeviceConfirm','Entfernen')}</button></div>`,'data-act="rmno"')}
const emptyPage=()=>`<div class="rp"><h1 class="rp-title">Radio Presets</h1><div class="ui-state rp-empty" role="status">${I('Speaker',32)}<h2>${t('presets.noDevicesTitle')}</h2><p>${t('presets.noDevicesHint')}</p><a class="btn btn-primary" href="#">${t('presets.goToSettings')}</a></div></div>`;
function render(quiet){
 const root=document.getElementById('root');let h='',ovl='';
 if(DEVN===0)h=shell(emptyPage(),'presets',false);
 else if(PG==='presets')h=shell(presetsPage(),'presets',false);
 else if(PG==='local')h=shell(localPage(),'none',false);
 else if(PG==='search'){h=searchPage();ovl=searchDialog()}
 else if(PG==='heads')h=shell(headsPage(),'none',false);
 else if(PG==='np')h=shell(npPage(),'none',false);
 else if(PG==='motion')h=shell(motionPage(),'none',false);
 const fk=document.activeElement&&document.activeElement.dataset?document.activeElement.dataset.fk:null;
 const mn0=document.querySelector('.app-main'),st0=mn0?mn0.scrollTop:0,stk0=!!document.querySelector('.ds-bar[data-stuck]');
 if(S.rm&&DEVN)ovl+=confirmRm();if(TOASTMSG)ovl+=toast('success',TOASTMSG);
 root.innerHTML=h+ovl;
 /* 6e: render() replaces the whole page including <main>, which is the scroller. Keep its scroll position and the stuck state of the bar. */
 {const mn1=document.querySelector('.app-main');if(mn1&&st0)mn1.scrollTop=st0;const b1=stk0&&document.querySelector('.ds-bar');if(b1)b1.setAttribute('data-stuck','')}
 root.querySelectorAll('dialog.dlg').forEach(d=>{if(!d.open)d.showModal()});
 marquee2();fitNames();swipeInit();stickyInit();
 if(fk){const el=root.querySelector(`[data-fk="${fk}"]`);if(el)el.focus()}
 if(quiet)return;
 if(!B&&(PG==='presets'||PG==='local')){const el=document.querySelector('.ds-dots');if(el&&Math.abs(el.clientWidth-(S.dw||0))>0.5){S.dw=el.clientWidth;return render()}}
 if(PG==='np')measureNp();
 if(PG==='motion')fillMotion();
 if(PG==='search')measureSearch();
 if(PG==='presets'||PG==='local'){const ar=document.querySelector('.ds-arrow--prev');if(ar){const r=ar.getBoundingClientRect(),vh=innerHeight,ok=r.top>=64&&r.bottom<=vh-8;DIAG='Wechsel-Pfeile: y '+Math.round(r.top)+' bis '+Math.round(r.bottom)+' von '+vh+' px Fensterhöhe, '+(ok?'ohne Scrollen sichtbar, ':'NICHT im ersten Bildschirm, ')+(vh-r.bottom<48?'am unteren Rand':'Abstand zum unteren Rand '+Math.round(vh-r.bottom)+' px')}}
 if(false){const d=document.querySelector('.ds-dots'),b=d&&d.querySelector('.ds-dot');if(d&&b){const r=b.getBoundingClientRect(),rows=new Set([...d.querySelectorAll('.ds-dot')].map(x=>Math.round(x.getBoundingClientRect().top))).size;const dev=document.querySelector('.dne-btn,.dne-heading button');DIAG+=` · Punkte: ${d.querySelectorAll('.ds-dot').length} von ${DEVN} sichtbar, ${rows} Zeile(n), Ziel ${r.width.toFixed(1)} × ${r.height.toFixed(0)} px, Modus ${B?'alt':(d.className.match(/ds-dots--(\w+)/)||[])[1]}`+(dev?` · Name: ${dev.scrollWidth>dev.clientWidth+1||dev.querySelector('.dne-text--scrolling')?'Laufschrift':'passt'}`:'')}}
}
function act(a,b){
 if(a==='rm'){S.rm=true;render(true);return}
 if(a==='rmno'){S.rm=false;render(true);const f=document.querySelector('[data-act=rm]');if(f)f.focus();return}
 if(a==='rmok'){const n=dn(S.i);DEVL.splice(S.i,1);DEVN=DEVL.length;S.i=Math.min(S.i,Math.max(DEVN-1,0));S.rm=false;TOASTMSG=t('presets.deviceRemoved',{name:n});S.dw=0;render();clearTimeout(window.__tt);window.__tt=setTimeout(()=>{TOASTMSG='';render(true)},6000);return}
 if(a==='mplay'){playMotion(b.dataset.m);return}
 let n=S.i;if(a==='prev')n=S.i-1;if(a==='next')n=S.i+1;if(a==='dot')n=+b.dataset.i;
 go(n)}
document.addEventListener('click',e=>{const b=e.target.closest('button[data-act]');if(b)act(b.dataset.act,b)});

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
Promise.all([fetch('../app6c/de-texts.json').then(r=>r.json()),fetch('../app7/de-texts.json').then(r=>r.json()),fetch('i18n-stage8-additions.json').then(r=>r.json()),fetch('../app/i18n-stage5-additions.json').then(r=>r.json()),fetch('../app6/i18n-stage6-additions.json').then(r=>r.json()),fetch('i18n-stage6b-additions.json').then(r=>r.json())]).then(([a0,a1,x,b,c,d])=>{const a=merge(a0,a1);TX=merge(merge(merge(merge(a,x.de),b.de),c.de),d.de);render();requestAnimationFrame(()=>setTimeout(audit,500))}).catch(e=>{document.getElementById('root').textContent='Fehler: '+e});

/* ---------- 6d: device switch with leaving card, swipe, sticky bar ---------- */
const ST=!B&&P('sticky','off')==='on',LEAK=P('leak','0')==='1',SWIPE=!B&&P('swipe','on')==='on',RM=matchMedia('(prefers-reduced-motion: reduce)').matches||P('rm','0')==='1';
const TH_MAX=80,TH_FRAC=.25,V_MIN=.4,D_MIN=24,LOCK=10; /* px, share of card width, px/ms, px, px */
let LOG='',swallow=false,STIO=null;
function go(n){
 n=Math.max(0,Math.min(DEVN-1,n));if(n===S.i)return;
 const old=document.querySelector('.ds-viewport .ds-card:not([data-leaving])'),dir=n>S.i?1:-1,x0=old?parseFloat(old.style.getPropertyValue('--ds-x'))||0:0;
 const clone=old&&!B&&!RM?old.cloneNode(true):null;
 S.i=n;render();
 const vp=document.querySelector('.ds-viewport'),cur=vp&&vp.querySelector('.ds-card');
 if(clone&&vp&&cur){
  clone.dataset.leaving='1';['data-dragging','data-settle'].forEach(a=>clone.removeAttribute(a));
  const sh=clone.querySelector('.ds-card-shell');sh.dataset.state='leaving';sh.setAttribute('aria-hidden','true');sh.inert=true;
  clone.style.cssText='position:absolute;left:2px;top:2px;width:calc(100% - 4px);--ds-x:'+x0+'px;'+(LEAK?'pointer-events:auto!important;':'');
  const ao=[clone.animate({opacity:[1,0]},{duration:240,easing:'linear',fill:'forwards'}),clone.animate({transform:['translateX(0)','translateX('+(-dir*12)+'px)']},{duration:240,easing:'cubic-bezier(.4,0,1,1)',fill:'forwards'})];
  vp.appendChild(clone);if(!LEAK)ao[0].onfinish=()=>clone.remove();
  cur.animate({opacity:[0,1]},{duration:240,easing:'linear'});cur.animate({transform:['translateX('+(dir*24)+'px)','translateX(0)']},{duration:320,easing:'cubic-bezier(.33,1,.68,1)'});
 }
 setTimeout(audit,450)}
function swipeInit(){
 const vp=document.querySelector('.ds-viewport');if(!vp||!SWIPE)return;
 const ds=vp.closest('.ds');let s=null;
 const cur=()=>vp.querySelector('.ds-card:not([data-leaving])'),setX=(c,x)=>c.style.setProperty('--ds-x',x+'px'),thr=()=>Math.min(TH_MAX,vp.clientWidth*TH_FRAC);
 const cue=(dx,armed)=>{dx?ds.dataset.pull=dx<0?'next':'prev':delete ds.dataset.pull;armed?ds.dataset.armed='':delete ds.dataset.armed};
 vp.addEventListener('pointerdown',e=>{
  if(s||(e.pointerType==='mouse'&&e.button!==0))return;
  if(e.target.closest('.vs-track,[role=slider],input,textarea,select,.dne,.dne-btn,.np-marquee'))return;
  const c=cur();if(!c)return;s={id:e.pointerId,x:e.clientX,y:e.clientY,lx:e.clientX,lt:e.timeStamp,v:0,lock:'',dx:0,c}});
 vp.addEventListener('pointermove',e=>{
  if(!s||e.pointerId!==s.id)return;
  const dx=e.clientX-s.x,dy=e.clientY-s.y;
  if(!s.lock){if(Math.abs(dx)<LOCK&&Math.abs(dy)<LOCK)return;if(Math.abs(dx)<Math.abs(dy)*1.2){s=null;return}s.lock='x';s.c.dataset.dragging='';try{vp.setPointerCapture(e.pointerId)}catch(_){}}
  const dt=Math.max(1,e.timeStamp-s.lt);s.v=.7*s.v+.3*((e.clientX-s.lx)/dt);s.lx=e.clientX;s.lt=e.timeStamp;s.dx=dx;
  const edge=(dx>0&&S.i===0)||(dx<0&&S.i===DEVN-1);
  if(!RM)setX(s.c,edge?Math.sign(dx)*32*(1-Math.exp(-Math.abs(dx)/120)):dx);
  cue(dx,!edge&&Math.abs(dx)>=thr())});
 const end=e=>{
  if(!s||e.pointerId!==s.id)return;const q=s;s=null;if(q.lock!=='x')return;
  q.c.removeAttribute('data-dragging');cue(0,false);swallow=true;setTimeout(()=>swallow=false,0);
  const dx=q.dx,v=q.v,t=thr(),dir=dx<0?1:-1,can=dir>0?S.i<DEVN-1:S.i>0;
  const ok=e.type==='pointerup'&&can&&(Math.abs(dx)>=t||(Math.abs(dx)>=D_MIN&&Math.abs(v)>=V_MIN&&Math.sign(v)===Math.sign(dx)));
  LOG='Wischen '+Math.round(dx)+' px, '+v.toFixed(2).replace('.',',')+' px/ms (Schwelle '+Math.round(t)+' px / '+D_MIN+' px + '+V_MIN.toString().replace('.',',')+' px/ms) → '+(ok?'Gerät '+(S.i+dir+1):can?'zurück zu Gerät '+(S.i+1):'Rand, Gerät '+(S.i+1)+' bleibt');
  parent.postMessage({oct:'swipe',log:LOG},'*');
  if(ok)go(S.i+dir);else{q.c.dataset.settle='';setX(q.c,0);setTimeout(()=>q.c.removeAttribute('data-settle'),260)}};
 vp.addEventListener('pointerup',end);vp.addEventListener('pointercancel',end);
 vp.addEventListener('click',e=>{if(swallow){e.stopPropagation();e.preventDefault()}},true)}
function stickyInit(){
 if(!ST)return;const bar=document.querySelector('.ds-bar'),main=document.querySelector('.app-main');if(!bar||!main)return;
 if(STIO)STIO.disconnect();
 STIO=new IntersectionObserver(([e])=>bar.toggleAttribute('data-stuck',e.intersectionRatio<1&&e.boundingClientRect.top<=e.rootBounds.top+1),{root:main,rootMargin:'-1px 0px 0px 0px',threshold:[1]});STIO.observe(bar)}
/* synthetic touch drag for the prototype (dx px over about 200 ms; extra: pause ms before release, to test speed) */
window.demoSwipe=(dx,ms=200,target='.np-art')=>new Promise(res=>{
 const vp=document.querySelector('.ds-viewport'),el=vp&&vp.querySelector(target);if(!el)return res('kein Ziel');
 const r=el.getBoundingClientRect(),x0=r.left+r.width/2-dx/2,y=r.top+r.height/2,fire=(t,x)=>el.dispatchEvent(new PointerEvent(t,{pointerId:7,pointerType:'touch',isPrimary:true,bubbles:true,cancelable:true,clientX:x,clientY:y,button:0,buttons:t==='pointerup'?0:1}));
 fire('pointerdown',x0);const N=Math.max(4,Math.round(ms/16));let k=0;
 const tick=()=>{k++;fire('pointermove',x0+dx*k/N);if(k<N)setTimeout(tick,ms/N);else{fire('pointerup',x0+dx);setTimeout(()=>res(LOG),30)}};setTimeout(tick,16)});

window.addEventListener('error',e=>{window.__err=(window.__err||'')+e.message+' @'+e.lineno+'; '});

document.addEventListener('cancel',e=>{if(S.rm){e.preventDefault();act('rmno')}},true);

/* 9: demo behaviour of the keys: play/pause toggles, prev/next show the loading state for 700 ms */
document.addEventListener('click',e=>{const b=e.target.closest('.lc-transport .lc-key');if(!b||b.disabled)return;const id=b.dataset.test.replace('lc-','');
 if(id==='play'){Q.set('play',P('play','1')==='1'?'0':'1');render(true);const n=document.querySelector('[data-test=lc-play]');if(n)n.focus()}
 else{Q.set('k',id);render(true);const n=document.querySelector('[data-test=lc-'+id+']');setTimeout(()=>{Q.delete('k');render(true);const m=document.querySelector('[data-test=lc-'+id+']');if(m)m.focus()},700)}});
