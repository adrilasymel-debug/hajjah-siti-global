import hashlib
import io
from pathlib import Path
from uuid import uuid4
import boto3
from botocore.config import Config
from PIL import Image, ImageOps
from pypdf import PdfReader, PdfWriter
from fastapi import HTTPException
from .config import settings

Image.MAX_IMAGE_PIXELS = 30_000_000

def validate_file(data):
    if not data or len(data) > settings.upload_limit_mb * 1024 * 1024:
        raise HTTPException(422, f'Upload a non-empty file up to {settings.upload_limit_mb} MB')
    try:
        if data.startswith(b'%PDF-'):
            pdf = PdfReader(io.BytesIO(data), strict=True)
            if pdf.is_encrypted or not 1 <= len(pdf.pages) <= 50: raise ValueError()
            # Reject active content rather than serving script-bearing PDFs inline.
            if any(marker in data for marker in [b'/JavaScript', b'/JS', b'/Launch', b'/EmbeddedFile', b'/OpenAction', b'/AA']): raise ValueError()
            return 'application/pdf'
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in ['PNG','JPEG'] or image.width*image.height > 30_000_000: raise ValueError()
            image.verify()
            return 'image/png' if image.format == 'PNG' else 'image/jpeg'
    except Exception:
        raise HTTPException(422, 'Use a valid PDF, JPG or PNG. Password-protected PDFs, active content and oversized images are unsupported.')

def prepare_invoice_document(pages):
    """Validate invoice pages and combine multiple files into one safe PDF."""
    if not pages:
        raise HTTPException(422, 'Choose at least one invoice page')
    if len(pages) > settings.upload_max_pages:
        raise HTTPException(422, f'Upload at most {settings.upload_max_pages} invoice pages at a time')
    total_size=sum(len(data) for _,data in pages)
    if total_size > settings.upload_total_limit_mb * 1024 * 1024:
        raise HTTPException(422, f'Keep all invoice pages within {settings.upload_total_limit_mb} MB in total')
    validated=[(name,data,validate_file(data)) for name,data in pages]
    if len(validated)==1:
        name,data,mime=validated[0]
        return name,data,mime,1

    writer=PdfWriter()
    for _,data,mime in validated:
        if mime=='application/pdf':
            reader=PdfReader(io.BytesIO(data), strict=True)
            for page in reader.pages: writer.add_page(page)
        else:
            with Image.open(io.BytesIO(data)) as image:
                image=ImageOps.exif_transpose(image)
                image.thumbnail((2500,3500), Image.Resampling.LANCZOS)
                if image.mode!='RGB':
                    if image.mode=='RGBA':
                        background=Image.new('RGB',image.size,'white');background.paste(image,mask=image.getchannel('A'));image=background
                    else:image=image.convert('RGB')
                rendered=io.BytesIO();image.save(rendered,format='PDF',resolution=200.0)
            reader=PdfReader(io.BytesIO(rendered.getvalue()), strict=True)
            writer.add_page(reader.pages[0])
        if len(writer.pages)>settings.upload_max_pages:
            raise HTTPException(422, f'Upload at most {settings.upload_max_pages} invoice pages at a time')
    output=io.BytesIO();writer.write(output);document=output.getvalue()
    if len(document)>settings.upload_total_limit_mb * 1024 * 1024:
        raise HTTPException(422, 'Combined invoice document is too large')
    return 'invoice-pages.pdf',document,'application/pdf',len(writer.pages)

class Storage:
    def client(self):
        return boto3.client('s3', endpoint_url=settings.s3_endpoint_url or None, region_name=settings.aws_default_region,
                            config=Config(signature_version='s3v4',s3={'addressing_style':'path'},request_checksum_calculation='when_required',response_checksum_validation='when_required'))
    def put(self, data, mime):
        key = str(uuid4())
        if settings.storage_backend == 's3':
            extra={'ServerSideEncryption':settings.s3_server_side_encryption} if settings.s3_server_side_encryption else {}
            self.client().put_object(Bucket=settings.s3_bucket, Key=key, Body=data, ContentType=mime,**extra)
        else:
            settings.storage_path.mkdir(parents=True, exist_ok=True)
            (settings.storage_path/key).write_bytes(data)
        return key
    def get(self, key):
        if '/' in key or '\\' in key or '..' in key: raise ValueError('Invalid object key')
        if settings.storage_backend == 's3': return self.client().get_object(Bucket=settings.s3_bucket, Key=key)['Body'].read()
        return (settings.storage_path/key).read_bytes()
    def delete(self,key):
        if settings.storage_backend == 's3': self.client().delete_object(Bucket=settings.s3_bucket, Key=key)
        else: (settings.storage_path/key).unlink(missing_ok=True)

storage = Storage()
