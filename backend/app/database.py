from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def AsyncSessionFactory():
    """Creates a fresh engine+session for Celery tasks (avoids event loop conflicts)."""
    _engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_size=2)
    _session = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    return _session()


async def get_db():
    async with async_session() as session:
        yield session
