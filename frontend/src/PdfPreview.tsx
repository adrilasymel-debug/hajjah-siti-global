import {useEffect,useRef,useState} from 'react';
import {getDocument,GlobalWorkerOptions,type PDFDocumentProxy} from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import {ChevronLeft,ChevronRight} from 'lucide-react';
import {ErrorBox,Loading} from './ui';
GlobalWorkerOptions.workerSrc=workerUrl;

export default function PdfPreview({url,zoom}:{url:string,zoom:number}){
 const canvas=useRef<HTMLCanvasElement>(null),container=useRef<HTMLDivElement>(null);
 const [doc,setDoc]=useState<PDFDocumentProxy|null>(null),[page,setPage]=useState(1),[error,setError]=useState(''),[loading,setLoading]=useState(true),[width,setWidth]=useState(500);
 useEffect(()=>{const task=getDocument({url,withCredentials:true,isEvalSupported:false,useSystemFonts:true});let active=true;task.promise.then(d=>{if(active){setDoc(d);setPage(1)}}).catch(()=>{if(active){setError('Unable to preview this PDF. Use Open full document or Download.');setLoading(false)}});return()=>{active=false;void task.destroy()}},[url]);
 useEffect(()=>{if(!container.current)return;const observer=new ResizeObserver(entries=>setWidth(Math.max(200,entries[0].contentRect.width-2)));observer.observe(container.current);return()=>observer.disconnect()},[]);
 useEffect(()=>{if(!doc||!canvas.current)return;let active=true,task:{cancel:()=>void}|undefined;setLoading(true);doc.getPage(page).then(p=>{if(!active||!canvas.current)return;const base=p.getViewport({scale:1});const scale=width/base.width*zoom/100;const viewport=p.getViewport({scale:scale*window.devicePixelRatio});const c=canvas.current;c.width=viewport.width;c.height=viewport.height;c.style.width=viewport.width/window.devicePixelRatio+'px';c.style.height=viewport.height/window.devicePixelRatio+'px';const rendered=p.render({canvas:c,viewport});task=rendered;return rendered.promise}).then(()=>{if(active)setLoading(false)}).catch(e=>{if(active&&e.name!=='RenderingCancelledException'){setError('Unable to render this page. Download the original to view it.');setLoading(false)}});return()=>{active=false;task?.cancel()}},[doc,page,zoom,width]);
 return <div className="pdf-preview" ref={container}><div className="pdf-page-control"><button className="icon-btn" aria-label="Previous document page" disabled={page===1} onClick={()=>setPage(page-1)}><ChevronLeft size={16}/></button><span>Page {page} of {doc?.numPages||'…'}</span><button className="icon-btn" aria-label="Next document page" disabled={!doc||page===doc.numPages} onClick={()=>setPage(page+1)}><ChevronRight size={16}/></button></div><ErrorBox message={error}/>{loading&&<Loading/>}<canvas ref={canvas} aria-label={'Original invoice, page '+page} style={{display:loading?'none':'block'}}/></div>
}
