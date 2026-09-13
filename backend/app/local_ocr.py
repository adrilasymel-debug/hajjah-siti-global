"""Free OCR, using native Tesseract in Linux or Tesseract.js on Windows."""
import io
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from PIL import Image,ImageOps
from pypdf import PdfReader
from .config import settings

def recognize_image(image):
    image.draft('RGB',(2400,2400))
    image.thumbnail((2400,2400))
    image=ImageOps.exif_transpose(image).convert('RGB')
    settings.ocr_cache_path.mkdir(parents=True,exist_ok=True)
    # Cache-root temporary work avoids writing originals to shared system directories.
    with tempfile.TemporaryDirectory(dir=settings.ocr_cache_path) as folder:
        file=Path(folder)/'page.png';image.save(file)
        native=shutil.which(settings.tesseract_command)
        if native:
            cmd=[native,str(file),'stdout','-l',settings.ocr_languages,'--psm','3']
        else:
            node=shutil.which('node')
            if not node:raise RuntimeError('Install Tesseract or Node with the free OCR package')
            cmd=[node,str(Path(__file__).resolve().parents[1]/'ocr'/'recognize.cjs'),str(file),settings.ocr_languages,str(settings.ocr_cache_path.resolve())]
        result=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',timeout=75)
        if result.returncode:raise RuntimeError('Local OCR failed')
        return result.stdout

def read_document(data,mime):
    if mime!='application/pdf':
        with Image.open(io.BytesIO(data)) as image:return recognize_image(image)[:100000]
    reader=PdfReader(io.BytesIO(data));output=[];deadline=time.monotonic()+300
    settings.ocr_cache_path.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=settings.ocr_cache_path) as folder:
        source=Path(folder)/'invoice.pdf';source.write_bytes(data)
        for index,page in enumerate(reader.pages):
            if time.monotonic()>deadline:raise RuntimeError('Local OCR time limit reached; manual review is available')
            text=page.extract_text() or ''
            if len(text.strip())<30:
                prefix=Path(folder)/'page'
                result=subprocess.run(['pdftoppm','-f',str(index+1),'-l',str(index+1),'-scale-to','2200','-png','-singlefile',str(source),str(prefix)],capture_output=True,timeout=40)
                if result.returncode:raise RuntimeError('PDF page could not be rendered for OCR')
                with Image.open(str(prefix)+'.png') as image:text=recognize_image(image)
                Path(str(prefix)+'.png').unlink(missing_ok=True)
            output.append(text)
            if sum(len(t) for t in output)>100000:break
    return '\n'.join(output)[:100000]
