 /* banners.js v12 — страховка баннеров: если имя файла не нашлось,
   пробуем запасные варианты (playhub→play, premium→premiun и т.д.).
   На новых страницах (body[data-native-banners]) только лечит картинки,
   рейл и стили там уже встроены в index.html. */
(function(){
if(window.__bannersLoaded)return;window.__bannersLoaded=true;
var NATIVE=document.body&&document.body.dataset.nativeBanners;
var MAN={};
var ALT={
  playhub:['play.png','playhub.png'],
  play:['play.png'],
  premium:['premium.png','premiun.png'],
  free24:['free.png','free24.png'],
  free:['free.png'],
  stars:['stars.png'],
  cases:['cases.png'],
  wheel:['wheel.png'],
  up:['up.png'],
  mines:['mines.png'],
  welcome:['welcome.png','welcome.jpg']
};
function cands(id){
  var list=[];
  if(MAN[id])list.push(MAN[id]);
  (ALT[id]||[]).forEach(function(f){list.push(f)});
  list.push(id+'.png');
  var out=[];list.forEach(function(f){if(out.indexOf(f)<0)out.push(f)});
  return out;
}
function attach(im){
  var id=im.getAttribute('data-b');if(!id||im.__healed)return;im.__healed=true;
  im.onerror=null;
  var list=cands(id),i=0;
  im.addEventListener('error',function(){
    i++;
    if(i<list.length){im.src='/static/banners/'+list[i]+'?v=12'}
    else{var host=im.closest?im.closest('.brc,.pgame,.slide,.ccard'):null;if(host)host.classList.remove('has');if(im.parentNode)im.parentNode.removeChild(im)}
  });
}
function heal(){document.querySelectorAll('img[data-b]').forEach(attach)}
fetch('/static/banners/manifest.json?v=12').then(function(r){return r.ok?r.json():{}}).then(function(j){MAN=j||{};heal()}).catch(function(){heal()});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',heal);else heal();
/* легаси-страницы без native-баннеров: добавляем картинки на карточки игр */
if(!NATIVE){
  var MAP={cases:'cases',wheel:'wheel',upgrade:'up',mines:'mines'};
  function legacy(){
    document.querySelectorAll('.pgame[data-game]').forEach(function(c){
      var id=MAP[c.dataset.game];if(!id||c.querySelector('img.bimg'))return;
      var im=document.createElement('img');im.className='bimg';im.setAttribute('data-b',id);
      im.style.cssText='position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:.55;pointer-events:none;filter:blur(1.6px) brightness(.82) saturate(.9)';
      im.src='/static/banners/'+(MAN[id]||id+'.png')+'?v=12';
      c.insertBefore(im,c.firstChild);attach(im);
    });
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',legacy);else legacy();
}
})();