from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    environment: str = 'development'
    database_url: str = 'sqlite:///./development.db'
    frontend_origin: str = 'http://localhost:5173'
    storage_backend: str = 'local'
    storage_path: Path = Path('./private-files')
    s3_bucket: str = ''
    s3_endpoint_url: str | None = None
    aws_default_region: str = 'ap-southeast-1'
    session_hours: int = 12
    upload_limit_mb: int = 15
    company_name: str = 'HAJJAH SITI GLOBAL'
    business_type: str = 'Dried seafood'
    free_only: bool = True
    extraction_provider: str = 'rules'
    inline_worker: bool = False
    frontend_dist: str = ''
    database_schema: str = ''
    ocr_languages: str = 'eng'
    ocr_cache_path: Path = Path('./.ocr-cache')
    tesseract_command: str = 'tesseract'
    s3_server_side_encryption: str = ''
    ocr_endpoint: str = ''
    ocr_provider: str = 'local'
    ocr_api_key: str = ''
    extraction_endpoint: str = ''
    extraction_api_key: str = ''
    extraction_model: str = ''
    demo_password: str = ''

    def validate_production(self):
        if self.environment == 'production':
            if not self.database_url.startswith('postgresql+psycopg://'):
                raise ValueError('Production requires PostgreSQL with psycopg')
            if not self.frontend_origin.startswith('https://') or self.storage_backend != 's3' or not self.s3_bucket:
                raise ValueError('Production requires HTTPS and private S3 storage')
            if self.demo_password:
                raise ValueError('Demo seeding must be disabled in production')


settings = Settings()
settings.validate_production()
