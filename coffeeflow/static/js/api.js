export class ApiError extends Error {
  constructor(message, status=0, fields={}, code='network_error') { super(message); Object.assign(this,{status,fields,code}); }
}
let token=null;
let tokenPromise=null;
async function raw(path, options={}) {
  const controller=new AbortController();
  const timer=setTimeout(()=>controller.abort(),15000);
  try {
    const response=await fetch('/api/v1'+path,{...options,credentials:'same-origin',signal:controller.signal});
    const data=response.status===204 ? null : await response.json().catch(()=>null);
    if(!response.ok) throw new ApiError(data?.error?.message||`Помилка сервера (${response.status}).`,response.status,data?.error?.fields||{},data?.error?.code);
    if(response.status!==204 && data===null) throw new ApiError('Сервер повернув неочікувану відповідь.',502);
    return data;
  } catch(error) {
    if(error instanceof ApiError) throw error;
    throw new ApiError('Не вдалося отримати відповідь. Перевірте з’єднання або спробуйте пізніше.');
  } finally {clearTimeout(timer);}
}
async function csrf(force=false) {
  if(force) token=null;
  if(token) return token;
  if(!tokenPromise) tokenPromise=raw('/auth/csrf').then(data=>token=data.csrf_token).finally(()=>tokenPromise=null);
  return tokenPromise;
}
export async function api(path,{method='GET',body}={}) {
  const options={method,headers:{}};
  if(method!=='GET') options.headers['X-CSRFToken']=await csrf();
  if(body!==undefined){options.headers['Content-Type']='application/json';options.body=JSON.stringify(body);}
  let result;
  try {result=await raw(path,options);} catch(error) {
    // Only retry a CSRF rejection, which occurs before the business mutation.
    if(error.code!=='csrf_failed'||method==='GET') throw error;
    options.headers['X-CSRFToken']=await csrf(true);
    result=await raw(path,options);
  }
  if(result?.csrf_token) token=result.csrf_token;
  if(path==='/auth/logout') token=null;
  return result;
}
export async function all(path) {
  const items=[];let offset=0;
  while(true){const data=await api(`${path}${path.includes('?')?'&':'?'}limit=100&offset=${offset}`);items.push(...data.items);offset+=data.items.length;if(offset>=data.total||!data.items.length) return items;}
}
