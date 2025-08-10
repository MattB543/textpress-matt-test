from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import Column, DateTime, String, Text, create_engine, func, event
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
            # Ensure a reasonable statement timeout to avoid long-running inserts (ms)
            try:
                import os

                timeout_ms = int(os.environ.get("PG_STATEMENT_TIMEOUT_MS", "120000"))

                @event.listens_for(self._engine, "connect")
                def _set_pg_statement_timeout(dbapi_connection, connection_record):  # type: ignore[no-redef]
                    try:
                        cursor = dbapi_connection.cursor()
                        cursor.execute(f"SET statement_timeout TO {timeout_ms}")
                        cursor.close()
                    except Exception:
                        # Best-effort; if it fails, continue without altering server setting
                        try:
                            cursor.close()
                        except Exception:
                            pass
            except Exception:
                # Ignore failures setting timeout
                pass
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
        # Sanitize text to avoid DB text encoding issues (e.g., NUL bytes)
        def _sanitize(value: str | None) -> str | None:
            if value is None:
                return None
            if not isinstance(value, str):
                value = str(value)
            # Remove NUL bytes that Postgres text cannot store
            value = value.replace("\x00", "")
            return value

        html_body = _sanitize(html_body) or ""
        md_body = _sanitize(md_body)
        with Session(engine) as session:  # type: ignore[arg-type]
            doc = Document(id=uid, source_type=source_type, html_body=html_body, md_body=md_body)
            session.add(doc)
            session.commit()


def make_meta_store() -> Optional[MetaStore]:
    url = os.environ.get("DATABASE_URL")
    if not url:
        return None
    return MetaStore(engine_url=url)


