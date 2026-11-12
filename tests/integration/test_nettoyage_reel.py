import json
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, select

from la_gazette_des_sorciers import nettoyage_rss
from la_gazette_des_sorciers.database.db_models import ArticlesPropres, Rejets, Sources

pytestmark = pytest.mark.integration

SOURCE = "test_nettoyage_reel"


def test_nettoyage_lit_le_bucket_et_ecrit_base_et_rapport(s3, db, monkeypatch):
    client, bucket, _ = s3
    maintenant = datetime.now(UTC)
    jour = maintenant.date()
    cle_brute = f"xml/{jour.isoformat()}/test.xml"
    brut = {
        "source_id": SOURCE,
        "fetched_at": maintenant.isoformat(),
        "s3_key": cle_brute,
        "content": {
            "rss": {
                "channel": {
                    "item": [
                        {"title": "Un titre", "link": "https://exemple.fr/nettoyage-reel"},
                        {"title": "", "link": "https://exemple.fr/invalide"},
                    ]
                }
            }
        },
    }
    client.put_object(
        Bucket=bucket,
        Key=f"json/{jour.isoformat()}/test.json",
        Body=json.dumps(brut).encode("utf-8"),
    )
    db.merge(
        Sources(
            id=SOURCE,
            name=SOURCE,
            type="test",
            region="test",
            url_flux="https://exemple.fr/flux",
            conditions="",
            notes="",
            actif=False,
        )
    )
    db.commit()
    try:
        nettoyage_rss.nettoyer_jour(jour)

        articles = db.scalars(
            select(ArticlesPropres).where(ArticlesPropres.source_id == SOURCE)
        ).all()
        rejets = db.scalars(select(Rejets).where(Rejets.source_id == SOURCE)).all()
        assert [a.fichier_brut for a in articles] == [cle_brute]
        assert [r.regle for r in rejets] == ["R00_invalide"]

        rapport = client.get_object(Bucket=bucket, Key=f"rapports/qualite-{jour.isoformat()}.md")
        assert SOURCE in rapport["Body"].read().decode("utf-8")
    finally:
        db.rollback()
        db.execute(delete(ArticlesPropres).where(ArticlesPropres.source_id == SOURCE))
        db.execute(delete(Rejets).where(Rejets.source_id == SOURCE))
        db.execute(delete(Sources).where(Sources.id == SOURCE))
        db.commit()
