import {all} from './api.js';
import {cart,changeCart,removeCart,reconcile,total} from './state.js';
import {$,esc,money,toast,errorState,initCommon} from './ui.js';
initCommon();
let products=[],categories=[],selected=0,loaded=false;
const catalog=$('#catalog');
function drawProducts(){
 const query=$('#search').value.trim().toLocaleLowerCase('uk');
 const shown=products.filter(p=>(!selected||p.category_id===selected)&&`${p.name} ${p.description}`.toLocaleLowerCase('uk').includes(query));
 catalog.setAttribute('aria-busy','false');
 catalog.innerHTML=shown.length?shown.map(p=>`<article class="product-card"><div class="product-image"><img src="${esc(p.image_url||('/static/images/'+(/десерт|чиз|торт/i.test(p.name)?'cake':'coffee')+'.svg'))}" alt="" loading="lazy">${!p.is_available?'<span class="unavailable">Тимчасово немає</span>':''}</div><h3>${esc(p.name)}</h3><p>${esc(p.description||'Приготуємо для вашої паузи.')}</p><div class="product-bottom"><strong>${money(p.price_cents)}</strong><button type="button" class="add-button" data-add="${p.id}" aria-label="Додати ${esc(p.name)} до кошика" ${p.is_available?'':'disabled'}>+</button></div></article>`).join(''):`<div class="empty-state"><h2>${products.length?'Нічого не знайшли':'Меню ще готується'}</h2><p class="muted">${products.length?'Спробуйте іншу назву або категорію.':'Зазирніть трохи пізніше.'}</p></div>`;
 catalog.querySelectorAll('img').forEach(img=>img.addEventListener('error',()=>{img.src='/static/images/coffee.svg';},{once:true}));
}
function drawCart(){
 const lines=reconcile(cart(),products);
 $('#cart-items').innerHTML=lines.length?lines.map(x=>`<div class="cart-line"><div class="cart-line-top"><strong>${esc(x.product?.name||'Товар недоступний')}</strong><span class="small">${money((x.product?.price_cents||0)*x.quantity)}</span></div>${loaded&&(!x.product||!x.product.is_available)?'<span class="field-error">Приберіть недоступний товар</span>':''}<div class="cart-line-bottom"><div class="quantity"><button data-delta="-1" data-id="${x.product_id}" aria-label="Зменшити кількість ${esc(x.product?.name||'товару')}">−</button><span aria-label="Кількість">${x.quantity}</span><button data-delta="1" data-id="${x.product_id}" aria-label="Збільшити кількість ${esc(x.product?.name||'товару')}" ${x.quantity>=20?'disabled':''}>+</button></div><button class="remove" data-remove="${x.product_id}">Прибрати</button></div></div>`).join(''):'<div class="cart-empty"><span aria-hidden="true">⌑</span>Тут буде ваша улюблена кава.<br>Додайте щось із меню.</div>';
 $('#cart-total').textContent=money(total(lines));
 $('#checkout-link').setAttribute('aria-disabled',String(!lines.length||!loaded||lines.some(x=>!x.product?.is_available)));
}
async function load(){loaded=false;catalog.innerHTML='<p class="loading">Завантажуємо меню…</p>';catalog.setAttribute('aria-busy','true');drawCart();try{[products,categories]=await Promise.all([all('/products'),all('/categories')]);loaded=true;$('#categories').innerHTML=[{id:0,name:'Усе меню'},...categories].map(c=>`<button type="button" data-category="${c.id}" aria-pressed="${c.id===selected}">${esc(c.name)}</button>`).join('');drawProducts();drawCart();}catch(error){errorState(catalog,error,load);}}
catalog.addEventListener('click',event=>{const button=event.target.closest('[data-add]');if(!button)return;const id=Number(button.dataset.add);const found=cart().find(x=>x.product_id===id);if(found?.quantity>=20||(!found&&cart().length>=30)){toast('Максимум 20 одиниць товару та 30 різних позицій.');return;}changeCart(id,1);toast('Додано до кошика');});
$('#categories').addEventListener('click',event=>{const b=event.target.closest('[data-category]');if(!b)return;selected=Number(b.dataset.category);$('#categories').querySelectorAll('button').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));drawProducts();});
$('#search').addEventListener('input',()=>{if(loaded)drawProducts();});
$('#cart-items').addEventListener('click',event=>{const b=event.target.closest('button');if(!b)return;if(b.dataset.remove)removeCart(Number(b.dataset.remove));else if(b.dataset.delta){changeCart(Number(b.dataset.id),Number(b.dataset.delta));$(`#cart-items [data-id="${b.dataset.id}"][data-delta="${b.dataset.delta}"]`)?.focus();}});
$('#checkout-link').addEventListener('click',event=>{if(event.currentTarget.getAttribute('aria-disabled')==='true'){event.preventDefault();toast('Додайте доступні товари, щоб оформити замовлення.');}});
window.addEventListener('cartchange',drawCart);window.addEventListener('storage',()=>{drawCart();window.dispatchEvent(new Event('cartchange'));});
load();
