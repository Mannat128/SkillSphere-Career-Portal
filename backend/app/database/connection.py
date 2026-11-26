from sqlalchemy import create_engine
from app.core.config import settings
from app.database.tls import database_engine_options

engine = create_engine(
    settings.DATABASE_URL,
    **database_engine_options(settings.DATABASE_SSL_CA),
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
    pool_pre_ping=True,
    echo=False
)
