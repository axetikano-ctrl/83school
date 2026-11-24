 /* banners.js v3 — рейл баннеров + картинки на карточках игр и hero.
   Файлы: frontend/banners/<id>.png (или что указано в manifest.json).
   Нет файла — процедурный арт, ничего не ломается. */
(function(){
if(window.__bannersLoaded)return;window.__bannersLoaded=true;
var MAN={},V='?v=3';
var RAIL=[
 {id:'pvp',title:'PVP HUB',badge:'NEW',price:'SOLO · TEAM',go:'hub',icon:'i-play',h:[38,18]},
 {id:'play',title:'PLAY HUB',badge:'',price:'4 GAMES',go:'hub',icon:'i-play',h:[272,292]},
 {id:'free24',title:'FREE24',badge:'24H',price:'Free 24h',go:'cases',icon:'i-gift',h:[45,28]},
 {id:'free',title:'FREE',badge:'',price:'Free',go:'cases',icon:'i-ticket',h:[140,320]},
 {id:'farm',title:'FARM',badge:'',price:'0.1',go:'mines',icon:'i-gem',h:[150,165]},
 {id:'bf',title:'BLACK FRIDAY',badge:'ЛИМИТ',price:'3.5',go:'wheel',icon:'i-ticket',h:[45,45]}
];
var GAME_MAP={cases:'cases',wheel:'wheel',upgrade:'up',mines:'mines'};
var HERO_MAP=['pvp','cases','up'];
function url(id){return '/static/banners/'+(MAN[id]||id+'.png')+V}
function hsl(h,s,l){return 'hsl('+h+','+s+'%,'+l+'%)'}
var css=document.createElement('style');
css.textContent=''
+'.brailsec{margin:6px 2px 14px;display:flex;align-items:center;justify-content:space-between}'
+'.brailsec .t{font-size:20px;font-weight:900;display:flex;align-items:center;gap:9px}'
+'.brail{display:flex;gap:12px;overflow-x:auto;padding:4px 2px 14px;scroll-snap-type:x mandatory;margin-bottom:18px}'
+'.brail::-webkit-scrollbar{height:8px}'
+'.brail::-webkit-scrollbar-track{background:var(--card)}'
+'.brail::-webkit-scrollbar-thumb{background:linear-gradient(90deg,var(--vio),var(--mag));border-radius:8px}'
+'.brc{position:relative;flex:0 0 168px;height:210px;border-radius:18px;overflow:hidden;border:1px solid var(--line);cursor:pointer;scroll-snap-align:start;transition:transform .2s,box-shadow .2s;background:#0b0817}'
+'.brc:hover{transform:translateY(-4px);box-shadow:0 14px 34px rgba(139,92,246,.28)}'
+'.brc .bfb{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;transition:opacity .4s}'
+'.brc .bfb svg{width:74px;height:74px;opacity:.9;filter:drop-shadow(0 8px 20px rgba(0,0,0,.5))}'
+'.brc img.bimg{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:0;transition:opacity .4s}'
+'.brc.has img.bimg{opacity:1}'
+'.brc.has .bfb{opacity:0}'
+'.brc .ov{position:absolute;inset:0;background:linear-gradient(180deg,rgba(5,3,12,.15) 0%,transparent 35%,rgba(5,3,12,.82) 100%)}'
+'.brc .tt{position:absolute;left:12px;top:12px;font-family:Arial Black,Impact,sans-serif;font-style:italic;font-weight:900;font-size:19px;color:#fff;text-shadow:0 2px 10px rgba(0,0,0,.6);letter-spacing:.5px;z-index:2}'
+'.brc .bd{position:absolute;left:12px;top:40px;background:linear-gradient(135deg,#f59e0b,#fbbf24);color:#221200;font-size:9px;font-weight:900;letter-spacing:1px;border-radius:6px;padding:3px 8px;z-index:2}'
+'.brc .pr{position:absolute;left:12px;bottom:12px;background:rgba(20,17,34,.85);backdrop-filter:blur(6px);border:1px solid var(--line);border-radius:9px;padding:6px 10px;font-size:11px;font-weight:800;color:var(--text);z-index:2}'
+'.brc .go{position:absolute;right:12px;bottom:12px;width:30px;height:30px;border-radius:9px;background:linear-gradient(135deg,var(--vio),var(--mag));display:flex;align-items:center;justify-content:center;color:#fff;z-index:2}'
+'.pgame img.bimg,.slide img.bimg{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:0;transition:opacity .5s;pointer-events:none}'
+'.pgame.has img.bimg{opacity:.5}'
+'.slide.has img.bimg{opacity:.34}'
+'.pgame .nm,.pgame .sb,.pgame .go,.pgame .live,.slide .t,.slide .s,.slide .cta{position:relative;z-index:2}'
;
document.head.appendChild(css);
function imgTag(id){return '<img class="bimg" alt="" src="'+url(id)+'">'}
function watch(host){
 var im=host.querySelector('img.bimg');if(!im)return;
 function ok(){host.classList.add('has')}
 function bad(){host.classList.remove('has');if(im.parentNode)im.parentNode.removeChild(im)}
 if(im.complete){im.naturalWidth>0?ok():bad()}
 else{im.addEventListener('load',ok);im.addEventListener('error',bad)}
}
function nav(go){
 try{
  if(typeof window.show==='function'){window.show('play')}
  else{var nb=document.querySelector('nav button[data-tab="play"]');if(nb)nb.click()}
  if(go==='hub'){if(typeof window.showHub==='function')window.showHub()}
  else if(typeof window.showGame==='function')window.showGame(go);
  else{var gc=document.querySelector('.pgame[data-game="'+go+'"]');if(gc)gc.click()}
 }catch(e){}
}
function buildRail(){
 if(document.getElementById('bannerRail'))return;
 var hero=document.querySelector('#shopScreen .hero');if(!hero)return;
 var sec=document.createElement('div');sec.className='brailsec';
 sec.innerHTML='<span class="t"><span class="livedot"></span>Баннеры и хабы</span>';
 var rail=document.createElement('div');rail.className='brail';rail.id='bannerRail';
 rail.innerHTML=RAIL.map(function(b){
  return '<div class="brc" data-id="'+b.id+'" data-go="'+b.go+'">'
   +'<div class="bfb" style="background:radial-gradient(80% 70% at 50% 40%,'+hsl(b.h[0],80,26)+' 0%,#0b0817 75%)"><svg style="color:'+hsl(b.h[0],90,62)+'"><use href="#'+b.icon+'"/></svg></div>'
   +imgTag(b.id)
   +'<div class="ov"></div><div class="tt">'+b.title+'</div>'
   +(b.badge?'<div class="bd">'+b.badge+'</div>':'')
   +'<div class="pr">'+b.price+'</div>'
   +'<div class="go"><svg class="ic" style="width:15px;height:15px"><use href="#i-play"/></svg></div></div>'
 }).join('');
 hero.insertAdjacentElement('afterend',sec);sec.insertAdjacentElement('afterend',rail);
 rail.querySelectorAll('.brc').forEach(function(c){
  c.addEventListener('click',function(){nav(c.dataset.go)});
  watch(c);
 });
}
function enhance(){
 buildRail();
 document.querySelectorAll('.pgame[data-game]').forEach(function(c){
  var id=GAME_MAP[c.dataset.game];if(!id||c.querySelector('img.bimg'))return;
  c.insertAdjacentHTML('afterbegin',imgTag(id));watch(c);
 });
 document.querySelectorAll('#slides .slide').forEach(function(s,i){
  var id=HERO_MAP[i];if(!id||s.querySelector('img.bimg'))return;
  s.insertAdjacentHTML('afterbegin',imgTag(id));watch(s);
 });
}
function refreshSrcs(){
 document.querySelectorAll('.brc').forEach(function(c){var im=c.querySelector('img.bimg');if(im){c.classList.remove('has');im.src=url(c.dataset.id);watch(c)}});
 document.querySelectorAll('.pgame[data-game]').forEach(function(c){var im=c.querySelector('img.bimg');var id=GAME_MAP[c.dataset.game];if(im&&id){c.classList.remove('has');im.src=url(id);watch(c)}});
 document.querySelectorAll('#slides .slide').forEach(function(s,i){var im=s.querySelector('img.bimg');var id=HERO_MAP[i];if(im&&id){s.classList.remove('has');im.src=url(id);watch(s)}});
}
fetch('/static/banners/manifest.json'+V).then(function(r){return r.ok?r.json():{}}).then(function(j){MAN=j||{};refreshSrcs()}).catch(function(){});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',enhance);else enhance();
})();