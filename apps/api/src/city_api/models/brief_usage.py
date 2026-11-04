"""Daily World Brief call counter, shared across API machines (CITY-679)."""

from datetime import date

from sqlalchemy import Date, Integer
from sqlalchemy.orm import Mapped, mapped_column

from city_api.database import Base


class BriefUsage(Base):
    __tablename__ = "brief_usage"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
