from pathlib import Path

import pytest

from la_gazette_des_sorciers.database.crud_sources import list_sources, upsert_sources
from la_gazette_des_sorciers.database.import_sources import UPDATE_COLUMNS, read_csv

pytestmark = pytest.mark.integration

# le paquet peut être installé hors du dépôt en CI, on vise le csv du dépôt
CSV_PATH = Path(__file__).resolve().parents[2] / "sources.csv"


def test_import_des_sources_depuis_le_csv(db):
    lignes = read_csv(CSV_PATH)

    upsert_sources(db, lignes, UPDATE_COLUMNS)
    sources = list_sources(db)

    assert {source.id for source in sources} >= {ligne["id"] for ligne in lignes}


def test_import_rejoue_ne_cree_pas_de_doublon(db):
    lignes = read_csv(CSV_PATH)
    upsert_sources(db, lignes, UPDATE_COLUMNS)
    avant = len(list_sources(db))

    upsert_sources(db, lignes, UPDATE_COLUMNS)

    assert len(list_sources(db)) == avant
