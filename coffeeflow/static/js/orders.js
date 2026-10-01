import {api} from './api.js';
import {read,rememberOrder} from './state.js';
import {$,esc,orderCard,busy,initCommon} from './ui.js';
initCommon();const list=$('#orders-list');let loading=false;
async function load(){
 if(loading)return;loading=true;busy($('#refresh-orders'),true);list.setAttribute('aria-busy','true');list.innerHTML='<p class="loading">Завантажуємо замовлення…</p>';
 try{const specific=Number(list.dataset.orderId);const stored=read('coffeeflow.orders',[]);const ids=specific?[specific]:(Array.isArray(stored)?stored:[]).filter(x=>Number.isSafeInteger(x)&&x>0).slice(0,20);
 if(!ids.length){list.innerHTML='<div class="empty-state"><h2>Ваша перша кава ще попереду</h2><p class="muted">Тут з’являться замовлення, оформлені в цьому браузері.</p><a class="button primary" href="/">Обрати каву</a></div>';return;}
 const results=await Promise.allSettled(ids.map(id=>api('/orders/'+id)));
 list.innerHTML=results.map((result,i)=>{if(result.status==='fulfilled'){rememberOrder(result.value.id);return orderCard(result.value);}return `<div class="message error" role="alert">Замовлення №${ids[i]}: ${esc(result.reason.status===404?'Не знайдено або недоступне в цій сесії.':result.reason.message)}</div>`;}).join('');
 if(specific&&new URLSearchParams(location.search).has('created')&&results[0]?.status==='fulfilled')list.insertAdjacentHTML('afterbegin','<p class="message success" role="status">Дякуємо! Ваше замовлення отримано. Збережіть цю сторінку.</p>');
 }finally{loading=false;busy($('#refresh-orders'),false);list.setAttribute('aria-busy','false');}
}
$('#refresh-orders').onclick=load;load();
