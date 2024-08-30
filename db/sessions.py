from sqlalchemy.orm import declarative_base
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_scoped_session,
    async_sessionmaker,
)
from typing import Any, AsyncGenerator
from asyncio import current_task
import os

# Static PostgreSQL Database URL
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

# Create the async engine
async_engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL, echo=True, future=True  # Optional: logs SQL statements
)


# Create an async session
async def create_async_session() -> async_scoped_session[AsyncSession]:
    async_session = async_scoped_session(
        async_sessionmaker(
            autocommit=False,
            autoflush=False,
            class_=AsyncSession,
            bind=async_engine,
            expire_on_commit=False,
        ),
        scopefunc=current_task,
    )

    return async_session


# Dependency to get async session
async def get_async_session() -> AsyncGenerator[AsyncSession, Any]:
    Session = await create_async_session()
    async with Session() as session:
        try:
            yield session
        finally:
            await session.close()


# Base class for declarative models
Base: Any = declarative_base()
