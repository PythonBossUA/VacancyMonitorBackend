import threading

from typing import Annotated

from fastapi import FastAPI, Query, Depends, HTTPException, status
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session
from models import Company, Vacancy, StatusEnum

app = FastAPI(
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)
DATABASE = Annotated[AsyncSession, Depends(get_session)]
PAGE_SIZE = 50

@app.get("/")
async def get_scraped_data(
    database: DATABASE,

    search: str = Query(default=""),
    selected_category: str = Query(default=""),
    selected_status: StatusEnum = Query(default=""),
    selected_is_active: bool = Query(default=None),

    page: int = Query(default=1)
):
    categories = await database.scalars(
        select(Vacancy.category)
        .distinct(Vacancy.category)
        .order_by(Vacancy.category.asc())
    )

    count = await database.scalar(
        select(func.count(Vacancy.id))
    )

    total_count = (count + PAGE_SIZE - 1) // PAGE_SIZE
    if PAGE_SIZE * page > total_count:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The page does not exist."
        )

    stmt = (
        select(Vacancy)
        .join(Vacancy.company)
        .order_by(Vacancy.publication_date.desc())
    )

    if search:
        stmt = stmt.where(
            or_(
                Vacancy.name.ilike(f"%{search}%"),
                Company.name.ilike(f"%{search}%")
            )
        )

    if selected_category:
        stmt = stmt.where(
            Vacancy.category == selected_category
        )

    if selected_status == "none":
        stmt = stmt.where(
            Vacancy.status.is_(None)
        )
    elif selected_status:
        stmt = stmt.where(
            Vacancy.status == selected_status
        )

    if selected_is_active is not None:
        stmt = stmt.where(
            Vacancy.is_active == selected_is_active
        )

    stmt = (
        stmt
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    )
    vacancies = await database.scalars(stmt)

    return {
        "vacancies": len(vacancies),
        "total_count": total_count,
        "search_query": search,
        "categories": categories,
        "selected_category": selected_category,
        "selected_status": selected_status,
        "selected_is_active": selected_is_active,
        "status_choices": StatusEnum,
    }
