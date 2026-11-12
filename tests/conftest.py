import os

# la connexion n'est ouverte qu'à l'usage, une URL factice suffit pour importer les modules
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://test:test@localhost:5432/test")
