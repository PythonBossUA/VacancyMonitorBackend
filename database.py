import os

from typing import AsyncGenerator

from dotenv import load_dotenv

from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
load_dotenv()


DATABASE_URL = os.environ["DATABASE_URL"]
SYNC_DATABASE_URL = DATABASE_URL.replace("+aiosqlite", "")

async_engine = create_async_engine(DATABASE_URL, echo=True)
async_session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

sync_engine = create_engine(SYNC_DATABASE_URL, echo=True)
sync_session = sessionmaker(sync_engine, class_=Session, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
