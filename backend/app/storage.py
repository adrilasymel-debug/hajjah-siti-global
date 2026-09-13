import hashlib
import io
from pathlib import Path
from uuid import uuid4
import boto3
from botocore.config import Config
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader
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
