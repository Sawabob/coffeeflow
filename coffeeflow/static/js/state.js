const memory={},volatile=new Set();
export function read(key,fallback){if(volatile.has(key))return memory[key]??fallback;try{return JSON.parse(localStorage.getItem(key)||'null')??fallback;}catch{return memory[key]??fallback;}}
export function write(key,value){memory[key]=value;try{localStorage.setItem(key,JSON.stringify(value));volatile.delete(key);}catch{volatile.add(key);}}
export function cart(){const value=read('coffeeflow.cart',[]);return Array.isArray(value)?value.filter(x=>Number.isInteger(x?.product_id)&&x.product_id>0&&Number.isInteger(x.quantity)&&x.quantity>0&&x.quantity<=20).slice(0,30):[];}
export function saveCart(items){write('coffeeflow.cart',items);window.dispatchEvent(new Event('cartchange'));}
export function changeCart(id,delta){const items=cart();const found=items.find(x=>x.product_id===id);if(found){found.quantity=Math.min(20,found.quantity+delta);}else if(delta>0&&items.length<30){items.push({product_id:id,quantity:1});}saveCart(items.filter(x=>x.quantity>0));}
export function removeCart(id){saveCart(cart().filter(x=>x.product_id!==id));}
export function rememberOrder(id){const old=read('coffeeflow.orders',[]);write('coffeeflow.orders',[id,...(Array.isArray(old)?old:[]).filter(x=>x!==id)].slice(0,20));}
export function reconcile(items,products){const byId=new Map(products.map(p=>[p.id,p]));return items.map(item=>({...item,product:byId.get(item.product_id)}));}
export function total(lines){return lines.reduce((sum,line)=>sum+(line.product?.price_cents||0)*line.quantity,0);}
