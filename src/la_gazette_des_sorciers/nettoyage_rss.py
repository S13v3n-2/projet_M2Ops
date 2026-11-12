import argparse
import json
import logging
import os
import re
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from la_gazette_des_sorciers.collecte_json import lire_objet_s3
from la_gazette_des_sorciers.dedoublonnage import Dedoublonneur
from la_gazette_des_sorciers.normalisation import borner_extrait, nettoyer
from la_gazette_des_sorciers.rapport_qualite import (
    construire_rapport,
    deposer_rapport,
    ecrire_rapport,
)
from la_gazette_des_sorciers.regles import appliquer_regles
from la_gazette_des_sorciers.stockage_s3 import assurer_bucket, connecter_bronze

load_dotenv()

logger = logging.getLogger("nettoyage_rss")

MAX_AGE = timedelta(hours=24)
# marge pour les décalages d'horloge entre le site et nous
TOLERANCE_FUTUR = timedelta(hours=1)
# R00 = validité de la donnée (les règles éditoriales sont dans regles.py)
R00_INVALIDE = "R00_invalide"
R00_TROP_VIEUX = "R00_trop_vieux"
R00_DATE_FUTURE = "R00_date_future"
PARIS = ZoneInfo("Europe/Paris")
# Le Parisien : pas de pubDate, mais le lien finit par -jj-mm-aaaa-IDENTIFIANT.php
DATE_DANS_URL = re.compile(r"-(\d{2})-(\d{2})-(\d{4})-[A-Za-z0-9]+\.php$")


def en_liste(valeur) -> list:
    # xmltodict renvoie un dict s'il y a 1 seul <item>, une liste sinon
    if valeur is None:
        return []
    return valeur if isinstance(valeur, list) else [valeur]


def texte(valeur) -> str:
    # une balise avec attributs devient {"@attr": ..., "#text": ...}
    if isinstance(valeur, dict):
        valeur = valeur.get("#text")
    if not valeur:
        return ""
    return str(valeur).strip()


def nettoyer_texte(valeur) -> str:
    return nettoyer(texte(valeur))


def parser_date(valeur) -> datetime | None:
    brut = texte(valeur)
    if not brut:
        return None
    try:
        date = parsedate_to_datetime(brut)
    except (TypeError, ValueError):
        return None
    if date.tzinfo is None:
        date = date.replace(tzinfo=UTC)
    return date.astimezone(UTC)


def date_depuis_url(url: str) -> datetime | None:
    # le lien ne donne que le jour : on prend minuit, heure de Paris
    m = DATE_DANS_URL.search(url)
    if not m:
        return None
    jour, mois, annee = (int(g) for g in m.groups())
    try:
        return datetime(annee, mois, jour, tzinfo=PARIS).astimezone(UTC)
    except ValueError:
        return None


def choisir_date(item: dict, url: str, fetched_at: datetime) -> tuple[datetime, str]:
    # pubDate, sinon date dans le lien, sinon date de collecte
    if date := parser_date(item.get("pubDate")):
        return date, "pubDate"
    if date := date_depuis_url(url):
        return date, "url"
    return fetched_at, "collecte"


def nettoyer_item(item: dict, source_id: str, fetched_at: datetime) -> dict | None:
    titre = nettoyer_texte(item.get("title"))
    url = texte(item.get("link"))
    if not titre or not url:
        return None
    publie, date_source = choisir_date(item, url, fetched_at)
    return {
        "source_id": source_id,
        "title": titre,
        "url": url,
        "guid": texte(item.get("guid")) or url,
        "published_at": publie.isoformat(),
        "date_source": date_source,
        "description": borner_extrait(nettoyer_texte(item.get("description"))),
    }


def nettoyer_flux(data: dict) -> tuple[list[dict], list[dict], dict]:
    source_id = data["source_id"]
    fetched_at = datetime.fromisoformat(data["fetched_at"])
    contenu = data.get("content") or {}
    if "rss" not in contenu:
        logger.warning("source=%s format non géré (racine: %s)", source_id, list(contenu))
    items = en_liste((contenu.get("rss") or {}).get("channel", {}).get("item"))

    articles = []
    rejets = []
    stats = {
        "total": len(items),
        "invalides": 0,
        "trop_vieux": 0,
        "date_url": 0,
        "date_collecte": 0,
    }
    for item in items:
        article = nettoyer_item(item, source_id, fetched_at)
        if article is None:
            stats["invalides"] += 1
            rejets.append(
                {
                    "source_id": source_id,
                    "title": nettoyer_texte(item.get("title")),
                    "url": texte(item.get("link")),
                    "regle": R00_INVALIDE,
                }
            )
            continue
        publie = datetime.fromisoformat(article["published_at"])
        if publie - fetched_at > TOLERANCE_FUTUR:
            rejets.append({**article, "regle": R00_DATE_FUTURE})
            continue
        if fetched_at - publie > MAX_AGE:
            stats["trop_vieux"] += 1
            rejets.append({**article, "regle": R00_TROP_VIEUX})
            continue
        regle = appliquer_regles(article)
        if regle:
            rejets.append({**article, "regle": regle})
            continue
        if article["date_source"] != "pubDate":
            stats[f"date_{article['date_source']}"] += 1
        articles.append(article)
    return articles, rejets, stats


def en_utc_naif(valeur: str) -> datetime:
    # la base stocke des dates UTC sans fuseau (comme la table sources)
    return datetime.fromisoformat(valeur).astimezone(UTC).replace(tzinfo=None)


def lignes_pour_la_base(
    articles: list[dict], rejets: list[dict], data: dict
) -> tuple[list[dict], list[dict]]:
    collecte_le = en_utc_naif(data["fetched_at"])
    # en mode S3 le JSON porte s3_key, en mode disque filepath
    fichier_brut = data.get("s3_key") or data.get("filepath")
    lignes_articles = [
        {
            "source_id": a["source_id"],
            "url": a["url"],
            "guid": a["guid"],
            "title": a["title"],
            "description": a["description"],
            "published_at": en_utc_naif(a["published_at"]),
            "date_source": a["date_source"],
            "collecte_le": collecte_le,
            "fichier_brut": fichier_brut,
        }
        for a in articles
    ]
    lignes_rejets = [
        {
            "source_id": r["source_id"],
            "url": r["url"],
            "title": r["title"],
            "regle": r["regle"],
            "collecte_le": collecte_le,
            "fichier_brut": fichier_brut,
        }
        for r in rejets
    ]
    return lignes_articles, lignes_rejets


def stocker_propre(articles: list[dict], data: dict, clean_dir: Path) -> Path:
    fetched_at_str = data["fetched_at"]
    dossier = clean_dir / datetime.fromisoformat(fetched_at_str).strftime("%Y-%m-%d")
    dossier.mkdir(parents=True, exist_ok=True)
    horodatage = datetime.fromisoformat(fetched_at_str).astimezone(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    chemin = dossier / f"{horodatage}_{data['source_id']}.json"
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=4)
    return chemin


def fichiers_du_jour(json_dir: Path, jour: date) -> list[Path]:
    # la collecte range les JSON dans un dossier par jour (date de collecte, UTC)
    return sorted((json_dir / jour.isoformat()).glob("*.json"))


def cles_du_jour_s3(client, bucket: str, jour: date) -> list[str]:
    prefixe = f"json/{jour.isoformat()}/"
    cles = []
    for page in client.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefixe):
        cles += [o["Key"] for o in page.get("Contents", []) if o["Key"].endswith(".json")]
    return sorted(cles)


def flux_du_jour(jour: date, client, bucket: str):
    """Renvoie le contenu de chaque JSON brut du jour, dans le bucket ou sur disque."""
    if client is not None:
        for cle in cles_du_jour_s3(client, bucket, jour):
            yield json.loads(lire_objet_s3(client, bucket, cle))
        return
    json_dir = Path(os.environ["DATA_DIR"]).resolve() / "json"
    for fichier in fichiers_du_jour(json_dir, jour):
        with open(fichier, encoding="utf-8") as f:
            yield json.load(f)


def nettoyer_jour(jour: date) -> None:
    client, bucket, region = connecter_bronze()
    resultats = []
    dedoublonneur = Dedoublonneur()
    # import ici : database.db lit DATABASE_URL dès l'import, ce qui casserait les tests
    from la_gazette_des_sorciers.database.crud_articles import inserer_articles, inserer_rejets
    from la_gazette_des_sorciers.database.db import SessionLocal

    for data in flux_du_jour(jour, client, bucket):
        articles, rejets, stats = nettoyer_flux(data)
        articles, doublons = dedoublonneur.filtrer(articles)
        rejets += doublons
        if client is None:
            clean_dir = Path(os.environ["DATA_DIR"]).resolve() / "clean"
            stocker_propre(articles, data, clean_dir)
        lignes_articles, lignes_rejets = lignes_pour_la_base(articles, rejets, data)
        with SessionLocal() as session:
            inserer_articles(session, lignes_articles)
            inserer_rejets(session, lignes_rejets)
        resultats.append(
            {
                "source_id": data["source_id"],
                "entres": stats["total"],
                "gardes": len(articles),
                "rejets": rejets,
            }
        )
        logger.info(
            "source=%s gardes=%d total=%d invalides=%d trop_vieux=%d rejetes=%d "
            "date_url=%d date_collecte=%d",
            data["source_id"],
            len(articles),
            stats["total"],
            stats["invalides"],
            stats["trop_vieux"],
            len(rejets),
            stats["date_url"],
            stats["date_collecte"],
        )

    if not resultats:
        logger.warning("aucun JSON collecté pour le %s", jour)
        return

    rapport = construire_rapport(resultats)
    if client is not None:
        assurer_bucket(client, bucket, region)
        cle = deposer_rapport(client, bucket, rapport, jour)
        logger.info("rapport de qualité déposé : s3://%s/%s", bucket, cle)
    else:
        rapports_dir = Path(os.environ.get("RAPPORTS_DIR", "rapports")).resolve()
        chemin = ecrire_rapport(rapport, jour, rapports_dir)
        logger.info("rapport de qualité écrit : %s", chemin)


def main():
    parser = argparse.ArgumentParser(description="Nettoyage des flux RSS d'un jour de collecte")
    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        help="jour de collecte à traiter, AAAA-MM-JJ (par défaut : aujourd'hui, UTC)",
    )
    nettoyer_jour(parser.parse_args().date or datetime.now(UTC).date())


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    main()
