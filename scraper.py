import httpx
import orjson

from datetime import date as datetime_date

from sqlalchemy import update
from sqlalchemy.dialects.sqlite import insert

from bs4 import BeautifulSoup

from database import sync_session
from models import Company, Vacancy, Category, vacancy_category_table

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


def scrap_data():
    current_year = datetime_date.today().year

    with httpx.Client(timeout=30) as client:
        with sync_session() as db_session:
            try:
                db_session.execute(update(Vacancy).values(is_active=False))

                vacancy_categories_res = client.get("https://jobs.dou.ua/")
                vacancy_categories_res.raise_for_status()

                csrf_token = vacancy_categories_res.cookies["csrftoken"]

                soap = BeautifulSoup(vacancy_categories_res.text, "html.parser")

                vacancy_objects = dict()
                categories = list()
                companies = set()
                for a_tag in soap.select("a.cat-link[href]"):
                    api_url = a_tag["href"].replace("?", "xhr-load/?")
                    category = a_tag.text

                    if category:
                        categories.append({"name": category})
                        data = {"csrfmiddlewaretoken": csrf_token, "count": 0}

                        while True:
                            response = client.post(
                                api_url, headers={"referer": api_url}, data=data
                            )
                            response.raise_for_status()

                            try:
                                vacancies_data = orjson.loads(response.content)
                                html_content = vacancies_data["html"]
                            except orjson.JSONDecodeError:
                                html_content = response.text

                            vacancy_soap = BeautifulSoup(html_content, "html.parser")
                            vacancy_blocks = vacancy_soap.select("li.l-vacancy")

                            for block in vacancy_blocks:
                                title = block.select_one("a.vt")

                                name = title.text.strip()
                                url = title["href"].strip().rsplit("?", 1)[0]

                                company_name = (
                                    block.select_one("strong > a")
                                    .text.strip(' "')
                                    .split("\xa0")[-1]
                                )
                                companies.add(company_name)

                                raw_date = block.select_one("div.date").text.strip()
                                day, month = raw_date.split(" ", 1)
                                date = datetime_date(
                                    year=current_year, month=MONTHS[month], day=int(day)
                                )

                                vacancy_object = vacancy_objects.get(url)
                                if vacancy_object:
                                    vacancy_object["categories"].add(category)
                                    continue

                                vacancy_objects[url] = {
                                    "name": name,
                                    "company": company_name,
                                    "publication_date": date,
                                    "categories": {category},
                                }

                            if vacancies_data.get("last"):
                                break
                            data["count"] += vacancies_data["num"]

                categories_dict = dict(
                    db_session.execute(
                        insert(Category)
                        .values(categories)
                        .on_conflict_do_update(
                            index_elements=("name",), set_={"id": Category.id}
                        )
                        .returning(Category.name, Category.id)
                    ).all()
                )

                companies_dict = dict(
                    db_session.execute(
                        insert(Company)
                        .values([{"name": company} for company in companies])
                        .on_conflict_do_update(
                            index_elements=("name",), set_={"id": Company.id}
                        )
                        .returning(Company.name, Company.id)
                    ).all()
                )
                vacancies_list = [
                    {
                        "name": data["name"],
                        "url": url,
                        "publication_date": data["publication_date"],
                        "company_id": companies_dict[data["company"]],
                    }
                    for url, data in vacancy_objects.items()
                ]
                vacancies_dict = dict(
                    db_session.execute(
                        insert(Vacancy)
                        .values(vacancies_list)
                        .on_conflict_do_update(
                            index_elements=("url",), set_={"is_active": True}
                        )
                        .returning(Vacancy.id, Vacancy.url)
                    ).all()
                )
                vacancy_categories_list = [
                    {
                        "vacancy_id": id_,
                        "category_id": categories_dict[category_name],
                    }
                    for id_ in vacancies_dict
                    for category_name in vacancy_objects[vacancies_dict[id_]][  # url
                        "categories"
                    ]
                ]
                db_session.execute(
                    insert(vacancy_category_table)
                    .values(vacancy_categories_list)
                    .on_conflict_do_nothing(
                        index_elements=("vacancy_id", "category_id")
                    )
                )
                db_session.commit()
            except Exception as e:
                ...
