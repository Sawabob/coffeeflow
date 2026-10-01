import {api,all} from './api.js';
import {$,esc,money,message,busy,toast,orderCard,initCommon} from './ui.js';
initCommon();let products=[],categories=[],editing=null,tab='orders',generation=0;
const dialog=$('#editor');
function signedOut(text=''){$('#admin-app').hidden=true;$('#logout').hidden=true;$('#login-form').hidden=false;$('#admin-loading').hidden=true;dialog.close();message($('#login-error'),text);}
function handleError(error,target=$('#admin-error')){if(error.status===401){signedOut('Сесія завершилася. Увійдіть ще раз.');}else message(target,error.message);}
async function load(){const current=++generation;message($('#admin-error'),'');const targets=['#admin-orders-list','#admin-product-list','#admin-category-list'];targets.forEach(s=>$(s).innerHTML='<p class="loading">Завантажуємо…</p>');try{
 const filter=$('#status-filter').value;const [newProducts,newCategories,orders]=await Promise.all([all('/products'),all('/categories'),all('/orders'+(filter?'?status='+encodeURIComponent(filter):''))]);if(current!==generation)return;products=newProducts;categories=newCategories;
 $('#admin-orders-list').innerHTML=orders.length?orders.map(o=>orderCard(o,true)).join(''):'<div class="empty-state"><h2>Поки без замовлень</h2><p class="muted">Нові замовлення з’являться тут після оновлення.</p></div>';
 $('#admin-product-list').innerHTML=products.length?products.map(p=>`<article class="panel"><p class="eyebrow">${esc(categories.find(c=>c.id===p.category_id)?.name||'Меню')}</p><h2>${esc(p.name)}</h2><p>${money(p.price_cents)} <span class="badge">${p.is_available?'Доступний':'Немає в наявності'}</span></p><div class="actions"><button class="button secondary" data-edit-product="${p.id}">Редагувати</button><button class="button secondary danger" data-delete-product="${p.id}">Прибрати з меню</button></div></article>`).join(''):'<p class="empty-state">Товарів ще немає. Додайте перший.</p>';
 $('#admin-category-list').innerHTML=categories.length?categories.map(c=>`<div class="category-row"><strong>${esc(c.name)}</strong><div class="actions"><button class="button secondary" data-edit-category="${c.id}">Редагувати</button><button class="button secondary danger" data-delete-category="${c.id}">Видалити</button></div></div>`).join(''):'<p class="empty-state">Додайте категорію перед створенням товарів.</p>';
 }catch(error){if(current!==generation)return;targets.forEach(s=>$(s).innerHTML='<p class="muted">Дані не завантажено. Натисніть «Оновити».</p>');handleError(error);}}
function signedIn(){$('#login-form').hidden=true;$('#admin-loading').hidden=true;$('#admin-app').hidden=false;$('#logout').hidden=false;$('#login-form').reset();load();}
async function check(){try{await api('/auth/me');signedIn();}catch(error){if(error.status===401)signedOut();else{$('#admin-loading').innerHTML='Не вдалося перевірити доступ. <button class="button secondary" id="retry-auth">Повторити</button>';$('#retry-auth').onclick=check;}}}
$('#login-form').addEventListener('submit',async event=>{event.preventDefault();const form=event.currentTarget,button=$('button[type=submit]',form);if(button.disabled)return;busy(button,true);message($('#login-error'),'');try{await api('/auth/login',{method:'POST',body:{username:form.elements.username.value,password:form.elements.password.value}});signedIn();}catch(error){message($('#login-error'),error.message);}finally{busy(button,false);}});
$('#logout').onclick=async()=>{busy($('#logout'),true);try{await api('/auth/logout',{method:'POST'});signedOut();}catch(error){handleError(error);}finally{busy($('#logout'),false);}};
$('#admin-refresh').onclick=load;$('#status-filter').onchange=load;
function switchTab(button){tab=button.dataset.tab;document.querySelectorAll('[data-tab]').forEach(b=>b.setAttribute('aria-selected',String(b===button)));['orders','products','categories'].forEach(name=>$(`#admin-${name}`).hidden=name!==tab);}
document.querySelectorAll('[data-tab]').forEach(button=>{button.onclick=()=>switchTab(button);button.onkeydown=event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();const tabs=[...document.querySelectorAll('[data-tab]')];let index=tabs.indexOf(button);index=event.key==='Home'?0:event.key==='End'?2:(index+(event.key==='ArrowRight'?1:2))%3;switchTab(tabs[index]);tabs[index].focus();};});
function openEditor(type,id=null){
 editing={type,id};const value=(type==='products'?products:categories).find(x=>x.id===id)||{};
 $('#editor-title').textContent=(id?'Редагувати':'Додати')+(type==='products'?' товар':' категорію');message($('#editor-error'),'');
 let html=`<label>Назва<input name="name" required maxlength="${type==='products'?120:80}" value="${esc(value.name||'')}"></label>`;
 if(type==='products'){
 if(!categories.length){toast('Спочатку додайте категорію.');return;}
 html+=`<label>Категорія<select name="category_id" required>${categories.map(c=>`<option value="${c.id}" ${c.id===value.category_id?'selected':''}>${esc(c.name)}</option>`).join('')}</select></label><label>Ціна, грн<input name="price" type="number" min="0.01" max="100000" step="0.01" required value="${value.price_cents?value.price_cents/100:''}"></label><label>Опис<textarea name="description" maxlength="2000" rows="2">${esc(value.description||'')}</textarea></label><label>Посилання на зображення <span class="muted">(необов’язково)</span><input name="image_url" type="url" maxlength="500" placeholder="https://…" value="${esc(value.image_url||'')}"></label><label class="checkbox"><input name="is_available" type="checkbox" ${value.is_available!==false?'checked':''}>Доступний для замовлення</label>`;
 }
 $('#editor-fields').innerHTML=html;dialog.showModal();$('input',dialog).focus();
}
$('#new-product').onclick=()=>openEditor('products');$('#new-category').onclick=()=>openEditor('categories');$('#close-editor').onclick=()=>dialog.close();
$('#editor-form').onsubmit=async event=>{event.preventDefault();const form=event.currentTarget,button=$('button[type=submit]',form);if(button.disabled)return;const info={...editing};const body={name:form.elements.name.value.trim()};if(info.type==='products')Object.assign(body,{category_id:Number(form.elements.category_id.value),price_cents:Math.round(Number(form.elements.price.value)*100),description:form.elements.description.value.trim(),image_url:form.elements.image_url.value.trim(),is_available:form.elements.is_available.checked});busy(button,true);$('#close-editor').disabled=true;message($('#editor-error'),'');try{await api('/'+info.type+(info.id?'/'+info.id:''),{method:info.id?'PATCH':'POST',body});dialog.close();toast('Зміни збережено');await load();}catch(error){handleError(error,$('#editor-error'));}finally{busy(button,false);$('#close-editor').disabled=false;}};
dialog.addEventListener('cancel',event=>{if($('#close-editor').disabled)event.preventDefault();});
$('#admin-app').addEventListener('click',async event=>{
 const b=event.target.closest('button');if(!b||b.disabled)return;
 if(b.dataset.editProduct){openEditor('products',Number(b.dataset.editProduct));return;}
 if(b.dataset.editCategory){openEditor('categories',Number(b.dataset.editCategory));return;}
 let path,method,body;
 if(b.dataset.deleteProduct){if(!confirm('Прибрати цей товар із меню? Історія замовлень збережеться.'))return;path='/products/'+b.dataset.deleteProduct;method='DELETE';}
 else if(b.dataset.deleteCategory){if(!confirm('Видалити порожню категорію?'))return;path='/categories/'+b.dataset.deleteCategory;method='DELETE';}
 else if(b.dataset.status){if(b.dataset.status==='cancelled'&&!confirm('Скасувати це замовлення?'))return;path='/orders/'+b.dataset.id;method='PATCH';body={status:b.dataset.status};}
 else return;
 busy(b,true);try{await api(path,{method,body});toast('Зміни збережено');await load();}catch(error){handleError(error);busy(b,false);}
});
check();
