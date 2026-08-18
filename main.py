import threading
from typing import Annotated

from fastapi import FastAPI, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession

app = FastAPI(
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)
DATABASE = Annotated[AsyncSession, Depends()]

async def get_scraped_data(
    search: str = Query(default=""),
    selected_category: str = Query(default=""),
    selected_status: str = Query(default=""),
    selected_is_active: bool = Query(default=None),
):
    ...

