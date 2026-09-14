import logging
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse,FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from .config import settings
from .db import get_db
from . import auth, purchasing, people, operations, wastage

@asynccontextmanager
async def lifespan(app):
    task=None
    if settings.inline_worker:
        from .worker import run_once
        async def consume():
            while True:
                try:await asyncio.to_thread(run_once)
                except Exception:logging.getLogger(__name__).exception('Invoice worker cycle failed')
                await asyncio.sleep(3)
        task=asyncio.create_task(consume())
    yield
    if task:
        task.cancel()
        try:await task
        except asyncio.CancelledError:pass

app=FastAPI(title='HAJJAH SITI GLOBAL API',version='1.1.0',lifespan=lifespan,docs_url='/api/docs' if settings.environment!='production' else None,redoc_url=None,openapi_url='/api/openapi.json' if settings.environment!='production' else None)
app.add_middleware(CORSMiddleware,allow_origins=[settings.frontend_origin],allow_credentials=True,allow_methods=['GET','POST','PUT','OPTIONS'],allow_headers=['Content-Type','X-CSRF-Token'])

@app.middleware('http')
async def security_headers(request:Request,call_next):
    if request.method in ['POST','PUT','PATCH','DELETE']:
        origin=request.headers.get('origin')
        if origin and origin!=settings.frontend_origin:return JSONResponse({'detail':'Untrusted origin'},status_code=403)
        try:length=int(request.headers.get('content-length','0'))
        except ValueError:return JSONResponse({'detail':'Invalid content length'},status_code=400)
        if length>(settings.upload_limit_mb+1)*1024*1024:return JSONResponse({'detail':'File is too large'},status_code=413)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff';response.headers['Referrer-Policy']='same-origin';response.headers['Cache-Control']='no-store'
    if settings.environment=='production':response.headers['Strict-Transport-Security']='max-age=31536000; includeSubDomains'
    return response

@app.exception_handler(IntegrityError)
async def integrity_error(request,exc):
    return JSONResponse({'detail':'This record conflicts with an existing record. Refresh and check for duplicates.'},status_code=409)

@app.exception_handler(Exception)
async def unexpected_error(request,exc):
    logging.getLogger(__name__).exception('Request failed: %s',request.url.path)
    return JSONResponse({'detail':'Something went wrong. Your changes were not completed; please try again.'},status_code=500)

@app.get('/api/health')
def health(db=Depends(get_db)):
    db.execute(text('SELECT 1'));return {'status':'ok','service':'family-operations'}

for router in [auth.router,purchasing.router,people.router,operations.router,wastage.router]:app.include_router(router,prefix='/api')

if settings.frontend_dist:
    dist=Path(settings.frontend_dist)
    app.mount('/assets',StaticFiles(directory=dist/'assets'),name='frontend-assets')
    @app.get('/{path:path}',include_in_schema=False)
    def frontend(path:str):
        if path.startswith('api/'):
            return JSONResponse({'detail':'Not found'},status_code=404)
        return FileResponse(dist/'index.html',headers={'Content-Security-Policy':"default-src 'self'; script-src 'self'; worker-src 'self' blob:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob:; connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'"})
