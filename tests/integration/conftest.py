import uuid
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from alembic import command
from la_gazette_des_sorciers.database.db import SessionLocal
from la_gazette_des_sorciers.stockage_s3 import connecter_bronze

RACINE = Path(__file__).resolve().parents[2]


@pytest.fixture
def s3(monkeypatch):
    """Client S3 réel sur un bucket jetable, supprimé en fin de test."""
    monkeypatch.setenv("S3_BUCKET", f"test-{uuid.uuid4().hex[:12]}")
    try:
        client, bucket, region = connecter_bronze()
    except ValueError as erreur:
        pytest.skip(f"S3 non configuré : {erreur}")
    if client is None:
        pytest.skip("S3_ENABLED est à false")
    try:
        yield client, bucket, region
    finally:
        try:
            for page in client.get_paginator("list_objects_v2").paginate(Bucket=bucket):
                for objet in page.get("Contents", []):
                    client.delete_object(Bucket=bucket, Key=objet["Key"])
            client.delete_bucket(Bucket=bucket)
        except Exception:
            # le bucket n'a peut-être jamais été créé
            pass


@pytest.fixture
def db():
    """Session sur la base réelle, migrée à la dernière révision."""
    try:
        with SessionLocal() as session:
            session.execute(text("select 1"))
    except OperationalError as erreur:
        pytest.skip(f"PostgreSQL injoignable : {erreur.__class__.__name__}")
    config = Config(str(RACINE / "alembic.ini"))
    config.set_main_option("script_location", str(RACINE / "alembic"))
    command.upgrade(config, "head")
    with SessionLocal() as session:
        yield session
