from enum import StrEnum, auto
from datetime import date

from sqlalchemy import String, Integer, Boolean, text, Date, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class StatusEnum(StrEnum):
    APPLIED = auto()
    NOT_INTERESTED = auto()


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(63), nullable=False, unique=True)

    vacancies: Mapped[list["Vacancy"]] = relationship(back_populates="company")


class Vacancy(Base):
    __tablename__ = "vacancies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(127), nullable=False)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    publication_date: Mapped[date] = mapped_column(Date, nullable=False)
    url: Mapped[str] = mapped_column(String(63), nullable=False, unique=True)
    category: Mapped[str] = mapped_column(String(31), nullable=False)
    status: Mapped[str | None] = mapped_column(
        Enum(StatusEnum, name="vacancy_status"),
        nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))

    company: Mapped[Company] = relationship(back_populates="vacancies")
