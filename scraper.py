import httpx
import orjson

from datetime import date as datetime_date

from sqlalchemy import update
from sqlalchemy.dialects.sqlite import insert

from bs4 import BeautifulSoup

from database import async_session
from models import Company, Vacancy

MONTHS = {
    "січня": 1,
    "лютого": 2,
    "березня": 3,
    "квітня": 4,
    "травня": 5,
    "червня": 6,
    "липня": 7,
    "серпня": 8,
    "вересня": 9,
    "жовтня": 10,
    "листопада": 11,
    "грудня": 12,
}


async def scrap_data():
    current_year = datetime_date.today().year
    cached_companies = {}

    with httpx.Client(timeout=30) as client:
        async with async_session() as db_session:
            try:
                await db_session.execute(
                    update(Vacancy)
                    .values(is_active=False)
                )

                vacancy_categories_res = client.get("https://jobs.dou.ua/")
                vacancy_categories_res.raise_for_status()

                csrf_token = vacancy_categories_res.cookies["csrftoken"]

                soap = BeautifulSoup(vacancy_categories_res.text, "html.parser")

                for a_tag in soap.select("a.cat-link[href]"):
                    api_url = a_tag["href"].replace("?", "xhr-load/?")
                    category = a_tag.text

                    if category:
                        data = {"csrfmiddlewaretoken": csrf_token, "count": 0}

                        while True:
                            response = client.post(api_url, headers={"referer": api_url}, data=data)
                            response.raise_for_status()

                            try:
                                vacancies_data = orjson.loads(response.content)
                                html_content = vacancies_data["html"]
                            except orjson.JSONDecodeError:
                                html_content = response.text

                            vacancy_soap = BeautifulSoup(html_content, "html.parser")
                            vacancy_blocks = vacancy_soap.select("li.l-vacancy")

                            vacancy_objects = []
                            for block in vacancy_blocks:
                                title = block.select_one("a.vt")

                                name = title.text.strip()
                                url = title["href"].strip().rsplit("?", 1)[0]

                                company_name = block.select_one("strong > a").text.strip()
                                company_id = cached_companies.get(company_name)
                                if not company_id:
                                    company_id = await db_session.scalar(
                                        insert(Company).values(
                                            name=company_name,
                                        )
                                        .on_conflict_do_update(
                                            index_elements=("name",),
                                            set_={"id": Company.id},
                                        )
                                        .returning(Company.id)
                                    )
                                    cached_companies[company_name] = company_id

                                raw_date = block.select_one("div.date").text.strip()
                                day, month = raw_date.split(" ", 1)
                                date = datetime_date(
                                    year=current_year, month=MONTHS[month], day=int(day)
                                )

                                vacancy_objects.append(
                                    {
                                        "name": name,
                                        "url": url,
                                        "company_id": company_id,
                                        "publication_date": date,
                                        "category": category
                                    }
                                )

                            await db_session.execute(
                                insert(Vacancy)
                                .values(vacancy_objects)
                                .on_conflict_do_update(index_elements=("url",), set_={"is_active": True})
                            )

                            if vacancies_data.get("last"):
                                break
                            data["count"] += vacancies_data["num"]

                await db_session.commit()
            except Exception as e:
                ...


import asyncio
asyncio.run(scrap_data())