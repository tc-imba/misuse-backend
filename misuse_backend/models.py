import pathlib

from sqlalchemy import Column, DateTime, func
from sqlmodel import Field, SQLModel, create_engine
from datetime import datetime


class History(SQLModel, table=True):
    id: int | None = Field(primary_key=True, nullable=False)
    method: str = Field(nullable=False)
    url: str = Field(nullable=False)
    client_ip: str = Field(nullable=False)
    client_geo: str = Field(nullable=False)
    created_at: datetime = Field(nullable=False)


sqlite_file_name = pathlib.Path.cwd() / "data" / "db.sqlite"
sqlite_file_name.parent.mkdir(parents=True, exist_ok=True)
sqlite_url = f"sqlite:///{sqlite_file_name.absolute()}"

engine = create_engine(sqlite_url, echo=True)
SQLModel.metadata.create_all(engine)
