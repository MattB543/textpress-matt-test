from __future__ import annotations

import os
from dataclasses import dataclass, field
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
    """Thin wrapper around a SQLAlchemy engine used to persist documents.

    The engine is created lazily and reused across requests. A short
    connection timeout is configured to avoid long hangs when the database is
    unreachable in hosted environments.
    """

    engine_url: str
    _engine: object | None = field(default=None, init=False, repr=False)

    def _get_engine(self):  # type: ignore[override]
        if self._engine is None:
            # psycopg2 supports connect_timeout (in seconds)
            self._engine = create_engine(
                self.engine_url,
                pool_pre_ping=True,
                connect_args={"connect_timeout": 5},
            )
            # Ensure tables exist once per process
            Base.metadata.create_all(self._engine)
        return self._engine

    def test_connection(self) -> None:
        engine = self._get_engine()
        # Use driver SQL to avoid requiring ORM mappings
        with engine.connect() as conn:  # type: ignore[attr-defined]
            conn.exec_driver_sql("SELECT 1")

    def create_document(
        self,
        *,
        uid: str,
        source_type: str,
        html_body: str,
        md_body: str | None,
    ) -> None:
        engine = self._get_engine()
        with Session(engine) as session:  # type: ignore[arg-type]
            doc = Document(id=uid, source_type=source_type, html_body=html_body, md_body=md_body)
            session.add(doc)
            session.commit()


def make_meta_store() -> Optional[MetaStore]:
    url = os.environ.get("DATABASE_URL")
    if not url:
        return None
    return MetaStore(engine_url=url)


