// Local WebAssembly OCR. Only public language assets are downloaded; invoice pixels stay local.
const { createWorker } = require(process.env.TESSERACT_JS_MODULE || 'tesseract.js');
(async()=>{
  const worker=await createWorker(process.argv[3]||'eng',1,{cachePath:process.argv[4]||'.ocr-cache',logger:()=>{}});
  try {const result=await worker.recognize(process.argv[2]);process.stdout.write(result.data.text);} finally{await worker.terminate()}
})().catch(()=>{process.stderr.write('Local OCR could not read the image.');process.exit(1)});
