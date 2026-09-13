import {useId} from 'react';
import {type Row} from './api';
import {useResource,useDebounce} from './ui';

export default function SupplierPicker({name,onChange}:{name:string,onChange:(name:string,id:string|null)=>void}){
 const listId=useId();const query=useDebounce(name);const {data,error}=useResource('/suppliers/lookup?q='+encodeURIComponent(query));
 const matches:Row[]=data||[];
 const existing=matches.find(s=>s.name.toLowerCase()===name.trim().toLowerCase());
 return <label className="full">Supplier <span className="required">*</span>
  <input aria-label="Supplier" required minLength={2} maxLength={200} autoComplete="off" list={listId} placeholder="Choose or type a new supplier name…" value={name} onChange={e=>{const value=e.target.value;const match=matches.find(s=>s.name.toLowerCase()===value.trim().toLowerCase());onChange(value,match?.id||null)}}/>
  <datalist id={listId}>{matches.map(s=><option key={s.id} value={s.name}/>)}</datalist>
  <span className="helper">{name.trim()?(existing?'Existing supplier selected.':'This name will be matched or added to your suppliers when you save.'):'Select an existing supplier or type a new name. New names are saved for future invoices.'}</span>
  {error&&<span className="warning-text">Suggestions are unavailable. You can still type the supplier name.</span>}
 </label>
}
