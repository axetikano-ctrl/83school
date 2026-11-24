 /* banners.js v5 — на новых страницах (body[data-native-banners]) ничего не делает:
   рейл и картинки уже встроены в index.html. На старых страницах — мягкий фолбэк. */
(function(){
if(window.__bannersLoaded)return;window.__bannersLoaded=true;
if(document.body&&document.body.dataset.nativeBanners)return;
var MAN={};
function url(id){return '/static/banners/'+(MAN[id]||id+'.png')+'?v=5'}
fetch('/static/banners/manifest.json?v=5').then(function(r){return r.ok?r.json():{}}).then(function(j){
 MAN=j||{};
 document.querySelectorAll('.pgame[data-game]').forEach(function(c){
  var map={cases:'cases',wheel:'wheel',upgrade:'up',mines:'mines'};var id=map[c.dataset.game];if(!id)return;
  var im=new Image();im.src=url(id);im.className='bimg';
  im.style.cssText='position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:.5;pointer-events:none';
  im.onload=function(){c.insertBefore(im,c.firstChild)};
 });
}).catch(function(){});
})();