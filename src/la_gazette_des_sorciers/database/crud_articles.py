from collections.abc import Iterable, Mapping
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from la_gazette_des_sorciers.database.db_models import ArticlesPropres, Rejets


def inserer_articles(session: Session, rows: Iterable[Mapping[str, Any]]) -> int:
    """Insère les articles propres. Un `url` déjà présent est ignoré (relance sans doublon)."""
    rows = list(rows)
    if not rows:
        return 0
    stmt = insert(ArticlesPropres).values(rows).on_conflict_do_nothing(index_elements=["url"])
    resultat = session.execute(stmt)
    session.commit()
    return resultat.rowcount


def inserer_rejets(session: Session, rows: Iterable[Mapping[str, Any]]) -> int:
    """Insère les rejets. Le couple (`url`, `regle`) déjà présent est ignoré."""
    rows = list(rows)
    if not rows:
        return 0
    stmt = insert(Rejets).values(rows).on_conflict_do_nothing(index_elements=["url", "regle"])
    resultat = session.execute(stmt)
    session.commit()
    return resultat.rowcount
