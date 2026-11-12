import json
import logging
import os
import sys
from datetime import UTC, datetime
from email.utils import format_datetime
from pathlib import Path

import requests
from dotenv import find_dotenv, load_dotenv

from la_gazette_des_sorciers.database.crud_sources import list_sources
from la_gazette_des_sorciers.database.db import SessionLocal
from la_gazette_des_sorciers.database.db_models import Sources

if __package__:
    from .stockage_s3 import assurer_bucket, connecter_bronze, deposer_contenu
else:
    from stockage_s3 import assurer_bucket, connecter_bronze, deposer_contenu

ENV_FILE = find_dotenv(usecwd=True)
load_dotenv(ENV_FILE)
BASE_DIR = Path(ENV_FILE).parent if ENV_FILE else Path.cwd()

logger = logging.getLogger("collecte_xml")

USER_AGENT = "Mozilla/5.0 (la_gazette_des_sorciers)"
TIMEOUT_S = 30

DATA_DIR = (BASE_DIR / os.getenv("DATA_DIR", "./data")).resolve()

XML_DATA_DIR = DATA_DIR / "xml"


def recuperer_sources() -> list[Sources]:
    with SessionLocal() as session:
        data = list_sources(session, actif=True)
    return data


def mettre_a_jour_source(source_id, etag=None, last_modified=None, derniere_reussite=None):
    with SessionLocal() as session:
        # on cherche une source par son id
        source_bdd = session.query(Sources).filter(Sources.id == source_id).first()
        if source_bdd:
            if etag:
                source_bdd.etag = etag
            if last_modified:
                source_bdd.last_modified = last_modified
            if derniere_reussite:
                source_bdd.derniere_reussite = derniere_reussite
            session.commit()


def fetch(source: Sources) -> tuple[bytes, int]:
    headers = {"User-Agent": USER_AGENT}

    if source.etag:
        headers["If-None-Match"] = source.etag
    if source.last_modified:
        # la date est déja en UTC il faut juste ajouter le tz
        last_modified_utc = source.last_modified.replace(tzinfo=UTC)
        headers["If-Modified-Since"] = format_datetime(last_modified_utc, usegmt=True)

    resp = requests.get(source.url_flux, headers=headers, timeout=TIMEOUT_S)
    resp.raise_for_status()

    headers = resp.headers
    etag = headers.get("etag")  # Récupération de l'en-tête ETag si présent
    last_modified = headers.get(
        "last-modified"
    )  # Récupération de l'en-tête Last-Modified si présent

    # on met à jour Etag, last-modified et la dernière réussite en BDD
    mettre_a_jour_source(
        source.id, etag=etag, last_modified=last_modified, derniere_reussite=datetime.now(UTC)
    )

    return resp.content, resp.status_code


def stocker(
    xml_data: bytes,
    source_id: str,
    source_url: str,
    fetched_at: datetime,
    status_code: int,
    client,
    bucket: str,
    region: str,
):

    jour = fetched_at.strftime("%Y-%m-%d")
    dossier_local = XML_DATA_DIR / jour
    fetched_at_str = fetched_at.isoformat()
    base_filename = f"{fetched_at.strftime('%Y%m%dT%H%M%S%fZ')}_{source_id}"
    xml_filepath = dossier_local / f"{base_filename}.xml"
    metadata_filepath = dossier_local / f"{base_filename}.json"
    xml_cle = f"xml/{jour}/{base_filename}.xml"
    metadata_cle = f"xml/{jour}/{base_filename}.json"
    metadata = {
        "source_id": source_id,
        "source_url": source_url,
        "fetched_at": fetched_at_str,
        "http_status": status_code,
    }

    if client is not None:
        metadata["s3_key"] = xml_cle
        metadata_contenu = json.dumps(metadata, ensure_ascii=False, indent=4).encode("utf-8")
        assurer_bucket(client, bucket, region)
        deposer_contenu(client, bucket, xml_cle, xml_data, "application/xml")
        deposer_contenu(client, bucket, metadata_cle, metadata_contenu, "application/json")
    else:
        # relatif à DATA_DIR : un chemin absolu ne vaut que sur la machine qui l'a écrit
        metadata["filepath"] = xml_filepath.relative_to(DATA_DIR).as_posix()
        metadata_contenu = json.dumps(metadata, ensure_ascii=False, indent=4).encode("utf-8")
        dossier_local.mkdir(parents=True, exist_ok=True)
        xml_filepath.write_bytes(xml_data)
        metadata_filepath.write_bytes(metadata_contenu)


def collecter_flux(source: Sources, client, bucket: str, region: str) -> None:

    # métadonnées
    fetched_at = datetime.now(UTC)
    source_id = source.id
    source_url = source.url_flux

    # data
    xml, status_code = fetch(source)

    # si code 304 (Not Modified), on ne stocke pas le fichier
    if status_code == 304:
        logger.info("Flux non modifié: %s", source.id)
        return

    stocker(
        xml,
        source_id,
        source_url,
        fetched_at,
        status_code,
        client,
        bucket,
        region,
    )
    logger.info("Flux collecté: %s", source.id)


def main():
    logger.info("XML data directory: %s", XML_DATA_DIR)
    sources = recuperer_sources()
    client, bucket, region = connecter_bronze()

    for source in sources:
        collecter_flux(source, client, bucket, region)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        # par default python est en stderr,
        # Kestra afficherait tous sortie stderr en logs ERROR,
        # donc on le passe en stdout
        stream=sys.stdout,
    )
    main()
