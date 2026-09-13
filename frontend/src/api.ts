export type Row = Record<string, any>;
let csrf = '';
export function setCsrf(value:string){ csrf=value; }
export async function api<T=any>(path:string, options:RequestInit={}):Promise<T>{
  const response=await fetch('/api'+path,{...options,credentials:'include',headers:{...(options.body instanceof FormData?{}:{'Content-Type':'application/json'}),'X-CSRF-Token':csrf,...options.headers}});
  if(!response.ok){ const data=await response.json().catch(()=>({}));if(response.status===401&&!path.startsWith('/auth/'))window.dispatchEvent(new Event('session-expired'));throw new Error(typeof data.detail==='string'?data.detail:Array.isArray(data.detail)?data.detail.map((x:Row)=>x.msg).join('; '):'Unable to complete this action. Please try again.');}
  return response.json();
}
export const post=(path:string,data:unknown={})=>api(path,{method:'POST',body:JSON.stringify(data)});
export const put=(path:string,data:unknown)=>api(path,{method:'PUT',body:JSON.stringify(data)});
export const currency=(value:unknown)=>new Intl.NumberFormat('en-MY',{style:'currency',currency:'MYR',minimumFractionDigits:2}).format(Number(value||0));
export const day=(value:unknown)=>value?new Date(String(value)).toLocaleDateString('en-MY',{day:'numeric',month:'short',year:'numeric'}):'—';
export const label=(value:string)=>value?.replaceAll('_',' ').replace(/^./,x=>x.toUpperCase())||'—';
export const today=()=>new Date().toLocaleDateString('en-CA');
