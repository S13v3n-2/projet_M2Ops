import json
import os
from datetime import UTC, datetime

import pytest

from la_gazette_des_sorciers.database.crud_sources import list_sources
from la_gazette_des_sorciers.database.db import SessionLocal
from la_gazette_des_sorciers.stockage_s3 import connecter_bronze

pytestmark = pytest.mark.e2e

# le cadrage demande au moins 8 sources couvertes
MIN_SOURCES = int(os.getenv("E2E_MIN_SOURCES", "8"))


@pytest.fixture(scope="module")
def bronze():
    client, bucket, _ = connecter_bronze()
    if client is None:
        pytest.skip("S3_ENABLED est à false")
    return client, bucket


def cles(client, bucket, prefixe):
    pages = client.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefixe)
    return [objet["Key"] for page in pages for objet in page.get("Contents", [])]


def test_les_sources_du_jour_sont_dans_le_bucket(bronze):
    client, bucket = bronze
    jour = datetime.now(UTC).strftime("%Y-%m-%d")

    xml = [k for k in cles(client, bucket, f"xml/{jour}/") if k.endswith(".xml")]
    conversions = cles(client, bucket, f"json/{jour}/")

    assert len(xml) >= MIN_SOURCES
    assert len(conversions) >= MIN_SOURCES


def test_les_json_contiennent_des_articles(bronze):
    client, bucket = bronze
    jour = datetime.now(UTC).strftime("%Y-%m-%d")

    for cle in cles(client, bucket, f"json/{jour}/"):
        document = json.loads(client.get_object(Bucket=bucket, Key=cle)["Body"].read())
        assert "content" in document, cle
        assert document["source_id"], cle


def test_la_base_enregistre_les_collectes_reussies():
    with SessionLocal() as session:
        reussies = [s for s in list_sources(session, actif=True) if s.derniere_reussite]

    assert len(reussies) >= MIN_SOURCES
