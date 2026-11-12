import os

import pytest
from dotenv import load_dotenv

# les tests d'intégration locaux lisent le .env du projet
load_dotenv()

# la connexion n'est ouverte qu'à l'usage, une URL factice suffit pour importer les modules
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://test:test@localhost:5432/test")


def pytest_collection_modifyitems(items):
    # tout ce qui n'est pas integration ou e2e est considéré comme unitaire
    for item in items:
        if not item.get_closest_marker("integration") and not item.get_closest_marker("e2e"):
            item.add_marker(pytest.mark.unit)
