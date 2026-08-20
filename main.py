import orjson

from typing import Annotated
from urllib.parse import urlencode

from fastapi import FastAPI, Query, Depends, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import select, or_, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager


from database import get_session
from models import Company, Vacancy, StatusEnum, Category
from scraper import scrap_data

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
DATABASE = Annotated[AsyncSession, Depends(get_session)]
PAGE_SIZE = 50

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://vacancy-monitor.onrender.com"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def get_scraped_data(
    request: Request,
    database: DATABASE,

    search: str = Query(default=""),
    category: str = Query(default=""),
    status: StatusEnum | str = Query(default=""),
    is_active: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
):
    query_params = {}

    stmt = (
        select(Vacancy)
        .join(Vacancy.company)
        .options(contains_eager(Vacancy.company))
        .order_by(Vacancy.id.asc())
    )

    if search:
        stmt = stmt.where(
            or_(Vacancy.name.ilike(f"%{search}%"), Company.name.ilike(f"%{search}%"))
        )
        query_params["search"] = search

    if category:
        stmt = stmt.where(
            Vacancy.categories.any(Category.name == category)
        )
        query_params["category"] = category

    if status:
        if status == "null":
            stmt = stmt.where(Vacancy.status.is_(None))
        else:
            stmt = stmt.where(Vacancy.status == status)

        query_params["status"] = status

    if is_active is not None:
        stmt = stmt.where(Vacancy.is_active == is_active)
        query_params["is_active"] = is_active

    stmt = stmt.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE + 1)
    vacancies = (await database.scalars(stmt)).all()

    path = request.url.path

    is_next_page = bool(vacancies.pop(-1) if len(vacancies) > PAGE_SIZE else False)
    is_previous_page = page > 1

    vacancies_json = [
        {
            "id": vacancy.id,
            "name": vacancy.name,
            "company_name": vacancy.company.name,
            "publication_date": vacancy.publication_date,
            "original_url": vacancy.url,
            "status": vacancy.status.value if vacancy.status else None,
            "is_active": vacancy.is_active
        }
        for vacancy in vacancies
    ]

    return {
        "vacancies": vacancies_json,
        "next_page": (
            f"{path}?{urlencode(query_params | {"page": page + 1})}"
            if is_next_page
            else None
        ),
        "previous_page": (
            f"{path}?{urlencode(query_params | {"page": page - 1})}"
            if is_previous_page
            else None
        ),
    }


@app.patch("/status/{vacancy_id}")
async def update_vacancy_status(request: Request, vacancy_id: int, database: DATABASE):
    data = orjson.loads(await request.body())
    status = data.get("status")

    enum_status = getattr(StatusEnum, status or "", None)

    await database.execute(
        update(Vacancy)
        .values({"status": enum_status})
        .where(Vacancy.id == vacancy_id)
    )
    return {"status": "OK"}


@app.get("/categories")
async def get_categories(database: DATABASE):
    return (
        await database.scalars(
            select(Category.name).distinct().order_by(Category.name.asc())
        )
    ).all()


@app.delete("/delete")
async def delete_all_inactive_vacancies(database: DATABASE):
    await database.execute(delete(Vacancy).where(Vacancy.is_active.is_(False)))
    return {"status": "OK"}


@app.post("/scrap")
async def start_scrap_data(bg: BackgroundTasks):
    bg.add_task(scrap_data)
    return {"status": "OK"}
