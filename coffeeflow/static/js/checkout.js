import {api,all} from './api.js';
import {cart,saveCart,reconcile,total,rememberOrder} from './state.js';
import {$,esc,money,message,errorState,busy,initCommon} from './ui.js';
initCommon();
const form=$('#checkout-form'),state=$('#checkout-state');let submitting=false,ready=false;
const localInput=date=>new Date(date.getTime()-date.getTimezoneOffset()*60000).toISOString().slice(0,16);
function times(){const now=Date.now();form.elements.pickup_at.min=localInput(new Date(now+16*60000));form.elements.pickup_at.max=localInput(new Date(now+7*86400000));if(!form.elements.pickup_at.value)form.elements.pickup_at.value=localInput(new Date(now+30*60000));}
async function load(){
 ready=false;$('#checkout-layout').hidden=true;state.hidden=false;state.innerHTML='<p class="loading">Перевіряємо кошик…</p>';
 if(!cart().length){state.innerHTML='<div class="empty-state"><h2>Кошик поки порожній</h2><p>Додайте щось смачне з меню.</p><a class="button primary" href="/">Перейти до меню</a></div>';return;}
 try{const products=await all('/products');const lines=reconcile(cart(),products);if(lines.some(x=>!x.product?.is_available)){state.innerHTML='<div class="message error" role="alert">Деякі товари більше недоступні. Оновіть кошик перед замовленням. <a class="text-link" href="/#menu">Змінити кошик</a></div>';return;}
 $('#summary-items').innerHTML=lines.map(x=>`<div class="cart-line row-between"><span>${esc(x.product.name)} <span class="muted">× ${x.quantity}</span></span><strong>${money(x.product.price_cents*x.quantity)}</strong></div>`).join('');$('#summary-total').textContent=money(total(lines));state.hidden=true;$('#checkout-layout').hidden=false;times();ready=true;
 }catch(error){errorState(state,error,load);}
}
form.addEventListener('submit',async event=>{
 event.preventDefault();if(submitting||!ready)return;
 message($('#form-error'),'');form.querySelectorAll('[data-error]').forEach(x=>x.textContent='');form.querySelectorAll('[aria-invalid]').forEach(x=>x.removeAttribute('aria-invalid'));
 times();if(!form.reportValidity())return;
 const pickup=new Date(form.elements.pickup_at.value);if(!Number.isFinite(pickup.getTime()))return;
 const data={customer_name:form.elements.customer_name.value.trim(),phone:form.elements.phone.value.trim(),pickup_at:pickup.toISOString(),comment:form.elements.comment.value.trim(),items:cart()};
 submitting=true;busy($('#place-order'),true,'Оформлюємо…');
 try{const order=await api('/orders',{method:'POST',body:data});rememberOrder(order.id);saveCart([]);location.assign(`/orders/${order.id}?created=1`);}
 catch(error){let text=error.message;if(error.status===0)text+=' Якщо запит міг надійти, уточніть у кав’ярні перед повторним оформленням.';message($('#form-error'),text);for(const [key,value] of Object.entries(error.fields)){const target=form.querySelector(`[data-error="${CSS.escape(key)}"]`);if(target){target.textContent=String(value);form.elements[key]?.setAttribute('aria-invalid','true');}}$('#form-error').scrollIntoView({block:'nearest'});}
 finally{submitting=false;busy($('#place-order'),false);}
});
window.addEventListener('storage',load);load();
