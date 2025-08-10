# app/meta.py - SIMPLIFIED VERSION
from __future__ import annotations

# pyright: reportMissingImports=false

import os
from typing import Optional

from sqlalchemy import Column, DateTime, String, Text, create_engine, func
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy.pool import NullPool
import logging

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

class MetaStore:
    def __init__(self, engine_url: str):
        self.engine_url = engine_url
        # Use NullPool for better connection management in web apps
        self.engine = create_engine(
            engine_url, 
            poolclass=NullPool,
            connect_args={"connect_timeout": 5}
        )
        Base.metadata.create_all(self.engine)
        self.logger = logging.getLogger("textpress.backend.meta")
        self.logger.info("DB engine initialized url=%s", self._redact(engine_url))
    
    def test_connection(self) -> None:
        with self.engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        self.logger.info("DB test connection OK")
    
    def create_document(
        self,
        uid: str,
        source_type: str,
        html_body: str,
        md_body: str | None,
    ) -> None:
        # Sanitize text
        html_body = (html_body or "").replace("\x00", "")
        if md_body:
            md_body = md_body.replace("\x00", "")
        
        with Session(self.engine) as session:
            doc = Document(
                id=uid,
                source_type=source_type,
                html_body=html_body,
                md_body=md_body
            )
            session.add(doc)
            session.commit()
            self.logger.info(
                "Inserted document uid=%s source_type=%s html_len=%s md_len=%s",
                uid,
                source_type,
                len(html_body),
                (len(md_body) if md_body else 0),
            )

    def _redact(self, url: str) -> str:
        # Avoid leaking credentials in logs
        try:
            if "@" in url and "://" in url:
                scheme, rest = url.split("://", 1)
                if "@" in rest:
                    creds, host = rest.split("@", 1)
                    if ":" in creds:
                        user, _ = creds.split(":", 1)
                    else:
                        user = creds
                    return f"{scheme}://{user}:***@{host}"
        except Exception:
            pass
        return url

def make_meta_store() -> Optional[MetaStore]:
    url = os.environ.get("DATABASE_URL")
    if not url:
        return None
    return MetaStore(engine_url=url)