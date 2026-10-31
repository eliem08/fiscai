"""Application configuration for FastAPI."""

import os

from pydantic import BaseModel


class Settings(BaseModel):
    env: str = os.getenv("ENVIRONMENT", "development")
    database_url: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/avenel")
    s3_endpoint: str = os.getenv("S3_ENDPOINT", "http://localhost:9000")
    s3_bucket: str = os.getenv("S3_BUCKET", "avenel-documents")


settings = Settings()
