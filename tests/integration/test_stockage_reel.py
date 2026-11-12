import json
from datetime import UTC, datetime

import pytest

from la_gazette_des_sorciers import collecte_json, collecte_xml

pytestmark = pytest.mark.integration

RSS = b"<rss><channel><title>demo</title><item><title>a</title></item></channel></rss>"


def test_aller_retour_xml_json_dans_le_bucket(s3):
    client, bucket, region = s3
    instant = datetime(2026, 10, 21, 8, 0, tzinfo=UTC)

    collecte_xml.stocker(RSS, "demo", "http://flux", instant, 200, client, bucket, region)
    cles_metadonnees = collecte_json.recuperer_fichiers_metadonnees(client, bucket)
    assert cles_metadonnees == ["xml/2026-10-21/20261021T080000000000Z_demo.json"]

    collecte_json.traiter_fichier(cles_metadonnees[0], client, bucket, region)

    sortie = client.get_object(
        Bucket=bucket, Key="json/2026-10-21/20261021T080000000000Z_demo.json"
    )
    document = json.loads(sortie["Body"].read())
    assert document["content"]["rss"]["channel"]["title"] == "demo"
    assert document["s3_key"] == "xml/2026-10-21/20261021T080000000000Z_demo.xml"
    assert "filepath" not in document


def test_depot_rejoue_remplace_les_objets(s3):
    client, bucket, region = s3
    instant = datetime(2026, 10, 21, 8, 0, tzinfo=UTC)
    for _ in range(2):
        collecte_xml.stocker(RSS, "demo", "http://flux", instant, 200, client, bucket, region)

    cles = [objet["Key"] for objet in client.list_objects_v2(Bucket=bucket)["Contents"]]
    assert len(cles) == 2
