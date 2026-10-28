import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from backend.app.config import settings

logger = logging.getLogger("tracepulse.database")

class Base(DeclarativeBase):
    pass

_engine = None
_sessionmaker = None

async def init_db_engine():
    global _engine, _sessionmaker
    if _engine is not None:
        return _engine

    target_url = settings.DATABASE_URL
    try:
        engine = create_async_engine(
            target_url,
            echo=False,
            pool_pre_ping=True,
            pool_recycle=3600,
            future=True
        )
        # Test connection
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info(f"Successfully connected to primary database: {target_url.split('@')[-1]}")
        _engine = engine
    except Exception as e:
        logger.warning(
            f"Failed to connect to primary database ({target_url.split('@')[-1]}): {e}. "
            f"Falling back to local SQLite engine: {settings.SQLITE_FALLBACK_URL}"
        )
        _engine = create_async_engine(
            settings.SQLITE_FALLBACK_URL,
            echo=False,
            future=True
        )

    _sessionmaker = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False
    )

    # Automatically initialize tables if not already present (supports SQLite fallback)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    return _engine

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    global _sessionmaker
    if _sessionmaker is None:
        await init_db_engine()
    async with _sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
