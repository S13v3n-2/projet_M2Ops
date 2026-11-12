from datetime import date

from la_gazette_des_sorciers.rapport_qualite import (
    construire_rapport,
    ecrire_rapport,
    rapport_en_markdown,
)

RESULTATS = [
    {
        "source_id": "a",
        "entres": 10,
        "gardes": 7,
        "rejets": [
            {"title": "Horoscope du jour", "regle": "R01_horoscope"},
            {"title": "Horoscope de demain", "regle": "R01_horoscope"},
            {"title": "vieux", "regle": "R00_trop_vieux"},
        ],
    },
    {
        "source_id": "b",
        "entres": 4,
        "gardes": 4,
        "rejets": [],
    },
]


def test_construire_rapport_compte_par_regle_et_par_source():
    rapport = construire_rapport(RESULTATS)
    assert (rapport["entres"], rapport["gardes"], rapport["rejetes"]) == (14, 11, 3)
    assert rapport["par_regle"] == {"R01_horoscope": 2, "R00_trop_vieux": 1}
    assert rapport["par_source"]["a"]["taux_rejet"] == 0.3
    assert rapport["par_source"]["b"]["taux_rejet"] == 0.0
    assert rapport["top_rejets"][0] == {"regle": "R01_horoscope", "source": "a", "nombre": 2}
    assert rapport["exemples"]["R01_horoscope"] == ["Horoscope du jour", "Horoscope de demain"]


def test_rapport_vide_ne_plante_pas():
    rapport = construire_rapport([])
    assert rapport["entres"] == 0
    assert rapport["top_rejets"] == []


def test_markdown_et_ecriture(tmp_path):
    rapport = construire_rapport(RESULTATS)
    texte = rapport_en_markdown(rapport, date(2026, 11, 12))
    assert "# Rapport de qualité — 2026-11-12" in texte
    assert "| R01_horoscope | 2 |" in texte
    chemin = ecrire_rapport(rapport, date(2026, 11, 12), tmp_path / "rapports")
    assert chemin.name == "qualite-2026-11-12.md"
    assert chemin.read_text(encoding="utf-8") == texte
