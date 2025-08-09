from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import Column, DateTime, String, Text, create_engine, func
from sqlalchemy.orm import DeclarativeBase, Session


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True)
    status = Column(String, nullable=False, default="published")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    source_type = Column(String, nullable=True)
    input_name = Column(String, nullable=True)
    html_body = Column(Text, nullable=False)
    md_body = Column(Text, nullable=True)


@dataclass
class MetaStore:
    engine_url: str
    def create_document(self, *, uid: str, source_type: str, html_body: str, md_body: str | None) -> None:
        engine = create_engine(self.engine_url)
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            doc = Document(id=uid, source_type=source_type, html_body=html_body, md_body=md_body)
            session.add(doc)
            session.commit()


def make_meta_store() -> Optional[MetaStore]:
    url = os.environ.get("DATABASE_URL")
    if not url:
        return None
    return MetaStore(engine_url=url)


