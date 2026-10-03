import {useState} from 'react';
import {Check,Plus} from 'lucide-react';
import {day,post,type Row} from '../api';
import {useAuth,useToast} from '../main';
import {Badge,Empty,ErrorBox,Form,Loading,Modal,PageHead,Pager,useResource} from '../ui';

const shortTime=(value:string)=>value?.slice(0,5)||'—';
const duration=(minutes:number)=>`${Math.floor(minutes/60)}h ${minutes%60}m`;

export function Overtime(){
 const {user}=useAuth(),boss=user.role==='BOSS';
 const [status,setStatus]=useState(''),[page,setPage]=useState(1),[refresh,setRefresh]=useState(0),[form,setForm]=useState(false),[review,setReview]=useState<Row|null>(null);
 const resource=useResource(`/overtime?status=${encodeURIComponent(status)}&page_number=${page}`,refresh),toast=useToast();
 const reload=()=>{setRefresh(value=>value+1);setReview(null)};
 return <>
  <PageHead eyebrow="PEOPLE" title="Overtime" description={boss?'Review same-day overtime submitted by staff before it is used for payroll decisions.':'Record completed overtime on the same day and keep its review status in view.'} actions={!boss&&<button className="button" onClick={()=>setForm(true)}><Plus size={17}/>Record today’s OT</button>}/>
  <section className="panel">
   <div className="filters"><select aria-label="Overtime status" value={status} onChange={event=>{setStatus(event.target.value);setPage(1)}}><option value="">All statuses</option><option value="submitted">Awaiting review</option><option value="approved">Approved</option><option value="rejected">Rejected</option></select></div>
   <ErrorBox message={resource.error}/>
   {resource.loading?<Loading/>:resource.data?.items.length?<><div className="table-wrap"><table><thead><tr>{boss&&<th>Staff</th>}<th>Date</th><th>Time</th><th>Net OT</th><th>Reason</th><th>Status</th>{boss&&<th/>}</tr></thead><tbody>{resource.data.items.map((entry:Row)=><tr key={entry.id}>{boss&&<td><strong>{entry.staff_name}</strong></td>}<td>{day(entry.work_date)}</td><td><strong>{shortTime(entry.start_time)}–{shortTime(entry.end_time)}</strong>{entry.break_minutes>0&&<small>{entry.break_minutes} min break</small>}</td><td><strong>{duration(entry.minutes)}</strong></td><td className="ot-reason">{entry.reason}</td><td><Badge value={entry.status}/>{entry.review_note&&<small>{entry.review_note}</small>}</td>{boss&&<td>{entry.status==='submitted'&&<button className="button secondary small" onClick={()=>setReview(entry)}>Review</button>}</td>}</tr>)}</tbody></table></div><Pager page={page} total={resource.data.total} onChange={setPage}/></>:<Empty title={boss?'No overtime submissions':'No overtime recorded yet'} text={boss?'Staff submissions will appear here for review.':'Use “Record today’s OT” after your overtime work is completed.'}/>}
  </section>
  {form&&<Modal title="Record today’s overtime" onClose={()=>setForm(false)}><p className="modal-copy"><strong>{resource.data?.today||'Today'}</strong> · Your name and today’s date are recorded automatically. Submit only after the OT has finished.</p><Form fields={[{key:'start_time',label:'OT start time',type:'time',required:true},{key:'end_time',label:'OT end time',type:'time',required:true},{key:'break_minutes',label:'Unpaid break (minutes)',type:'number',min:'0',step:'1'},{key:'reason',label:'Work completed / reason for OT',type:'textarea',required:true,full:true}]} initial={{break_minutes:0}} onCancel={()=>setForm(false)} onSave={async data=>{await post('/overtime',data);setForm(false);setRefresh(value=>value+1);toast('Overtime submitted for Boss review')}} submit="Submit OT proof"><p className="helper padded">The time must be for today in Malaysia, the end time must already have passed, and the net OT must be at least 15 minutes.</p></Form></Modal>}
  {review&&<Modal title="Review overtime proof" onClose={()=>setReview(null)}><div className="ot-review"><span className="entity-avatar">{review.staff_name.split(' ').map((part:string)=>part[0]).slice(0,2).join('')}</span><div><h3>{review.staff_name}</h3><p>{day(review.work_date)} · {shortTime(review.start_time)}–{shortTime(review.end_time)} · <strong>{duration(review.minutes)}</strong></p><p>{review.reason}</p></div></div><div className="form-actions"><button className="button" onClick={async()=>{await post(`/overtime/${review.id}/approve`);reload();toast('Overtime approved')}}><Check size={17}/>Approve OT</button></div><div className="ot-reject"><Form fields={[{key:'reason',label:'Reason for rejection',type:'textarea',required:true,full:true}]} onCancel={()=>setReview(null)} onSave={async data=>{await post(`/overtime/${review.id}/reject`,data);reload();toast('Overtime rejected')}} submit="Reject submission"/></div></Modal>}
 </>;
}
