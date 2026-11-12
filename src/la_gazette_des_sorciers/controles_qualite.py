"""Controles de qualite sur les donnees nettoyees du jour (TD 4).

Choix d'outil : assertions SQL maison en Python, pas Great Expectations ni Soda.
Il n'y a que trois controles et une seule base, une dependance de plus dans
l'image ne se justifie pas.

Metriques : une tache docker.Run de Kestra lit sur stdout les lignes
::{"metrics":[...]}:: et les enregistre comme metriques de la tache. Aucun client
ni service a ajouter, la ligne est ecrite avec print() et non via logging.
"""

import json
import logging
import sys
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import func, select

from la_gazette_des_sorciers.database.db_models import ArticlesPropres, Rejets
from la_gazette_des_sorciers.nettoyage_rss import TOLERANCE_FUTUR

logger = logging.getLogger("controles_qualite")

MAX_TAUX_REJET = 0.80


def collecter_faits(session, jour: date, maintenant: datetime) -> dict:
    # meme convention que le nettoyage : le jour UTC de collecte
    debut = datetime.combine(jour, time.min)
    fin = debut + timedelta(days=1)
    du_jour = ArticlesPropres.collecte_le >= debut, ArticlesPropres.collecte_le < fin

    par_source: dict[str, dict] = {}
    gardes = session.execute(
        select(ArticlesPropres.source_id, func.count())
        .where(*du_jour)
        .group_by(ArticlesPropres.source_id)
    )
    for source_id, nombre in gardes:
        par_source.setdefault(source_id, {"gardes": 0, "rejetes": 0})["gardes"] = nombre
    rejetes = session.execute(
        select(Rejets.source_id, func.count())
        .where(Rejets.collecte_le >= debut, Rejets.collecte_le < fin)
        .group_by(Rejets.source_id)
    )
    for source_id, nombre in rejetes:
        par_source.setdefault(source_id, {"gardes": 0, "rejetes": 0})["rejetes"] = nombre

    dates_futures = session.scalar(
        select(func.count()).where(
            *du_jour, ArticlesPropres.published_at > maintenant + TOLERANCE_FUTUR
        )
    )
    titres_vides = session.scalar(
        select(func.count()).where(*du_jour, func.trim(ArticlesPropres.title) == "")
    )
    return {
        "par_source": par_source,
        "dates_futures": dates_futures,
        "titres_vides": titres_vides,
    }


def taux_par_source(faits: dict) -> dict[str, float]:
    taux = {}
    for source_id, n in faits["par_source"].items():
        total = n["gardes"] + n["rejetes"]
        if total:
            taux[source_id] = n["rejetes"] / total
    return taux


def evaluer(faits: dict) -> list[dict]:
    taux = taux_par_source(faits)
    fautives = {s: t for s, t in sorted(taux.items()) if t > MAX_TAUX_REJET}
    detail = ", ".join(f"{s} ({t:.0%})" for s, t in fautives.items())
    taux_max = max(taux.values(), default=0.0)
    dates_futures = faits["dates_futures"]
    titres_vides = faits["titres_vides"]
    return [
        {
            "nom": "aucune_date_future",
            "ok": dates_futures == 0,
            "valeur": dates_futures,
            "message": f"{dates_futures} article(s) avec une date future (seuil : 0)",
        },
        {
            "nom": "aucun_titre_vide",
            "ok": titres_vides == 0,
            "valeur": titres_vides,
            "message": f"{titres_vides} article(s) avec un titre vide (seuil : 0)",
        },
        {
            "nom": "taux_rejet_par_source",
            "ok": not fautives,
            "valeur": taux_max,
            "message": (
                f"taux de rejet max {taux_max:.0%} (seuil : {MAX_TAUX_REJET:.0%})"
                + (f", sources fautives : {detail}" if fautives else "")
            ),
        },
    ]


def executer(session, jour: date, maintenant: datetime) -> dict:
    faits = collecter_faits(session, jour, maintenant)
    controles = evaluer(faits)
    return {
        "ok": all(c["ok"] for c in controles),
        "controles": controles,
        "metriques": {
            "dates_futures": faits["dates_futures"],
            "titres_vides": faits["titres_vides"],
            "taux_rejet_max": max(taux_par_source(faits).values(), default=0.0),
        },
    }


def metriques_kestra(metriques: dict, jour: date) -> str:
    liste = [
        {
            "name": f"gazette.controle.{cle}",
            "type": "counter",
            "value": valeur,
            "tags": {"jour": jour.isoformat()},
        }
        for cle, valeur in metriques.items()
    ]
    return "::" + json.dumps({"metrics": liste}, separators=(",", ":")) + "::"


def ouvrir_session():
    # import ici : database.db lit DATABASE_URL des l'import, ce qui casserait les tests
    from la_gazette_des_sorciers.database.db import SessionLocal

    return SessionLocal()


def main():
    maintenant = datetime.now(UTC).replace(tzinfo=None)
    with ouvrir_session() as session:
        resultat = executer(session, maintenant.date(), maintenant)
    for controle in resultat["controles"]:
        etat = "OK" if controle["ok"] else "ECHEC"
        logger.info("controle=%s %s : %s", controle["nom"], etat, controle["message"])
    print(metriques_kestra(resultat["metriques"], maintenant.date()), flush=True)
    if not resultat["ok"]:
        echecs = [f"{c['nom']} - {c['message']}" for c in resultat["controles"] if not c["ok"]]
        logger.error("controles de qualite en echec : %s", " ; ".join(echecs))
        sys.exit(1)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )
    main()
