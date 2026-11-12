from datetime import datetime

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Sources(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)
    type: Mapped[str] = mapped_column(nullable=False)
    region: Mapped[str] = mapped_column(nullable=False)
    url_flux: Mapped[str] = mapped_column(nullable=False)
    conditions: Mapped[str] = mapped_column(nullable=False)
    notes: Mapped[str] = mapped_column(nullable=False)
    actif: Mapped[bool] = mapped_column(nullable=False)
    derniere_reussite: Mapped[datetime] = mapped_column(nullable=True)
    echecs_consecutifs: Mapped[int] = mapped_column(nullable=True)
    etag: Mapped[str] = mapped_column(nullable=True)
    last_modified: Mapped[datetime] = mapped_column(nullable=True)


class ArticlesPropres(Base):
    __tablename__ = "articles_propres"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), nullable=False)
    url: Mapped[str] = mapped_column(unique=True, nullable=False)
    guid: Mapped[str] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(nullable=False)
    published_at: Mapped[datetime] = mapped_column(nullable=False)
    date_source: Mapped[str] = mapped_column(nullable=False)
    collecte_le: Mapped[datetime] = mapped_column(nullable=False)
    fichier_brut: Mapped[str] = mapped_column(nullable=False)


class Rejets(Base):
    __tablename__ = "rejets"
    __table_args__ = (UniqueConstraint("url", "regle"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), nullable=False)
    url: Mapped[str] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(nullable=False)
    regle: Mapped[str] = mapped_column(nullable=False, index=True)
    collecte_le: Mapped[datetime] = mapped_column(nullable=False)
    fichier_brut: Mapped[str] = mapped_column(nullable=False)