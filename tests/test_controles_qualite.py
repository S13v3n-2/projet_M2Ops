from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from la_gazette_des_sorciers import controles_qualite
from la_gazette_des_sorciers.controles_qualite import collecter_faits, evaluer, executer
from la_gazette_des_sorciers.database.db_models import ArticlesPropres, Base, Rejets, Sources

MAINTENANT = datetime(2026, 5, 4, 12, 0)
JOUR = MAINTENANT.date()


def faits(par_source=None, dates_futures=0, titres_vides=0):
    return {
        "par_source": par_source or {},
        "dates_futures": dates_futures,
        "titres_vides": titres_vides,
    }


def par_nom(controles):
    return {c["nom"]: c for c in controles}


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        for source_id in ("a", "b"):
            s.add(
                Sources(
                    id=source_id,
                    name=source_id,
                    type="rss",
                    region="fr",
                    url_flux="http://x",
                    conditions="",
                    notes="",
                    actif=True,
                )
            )
        s.commit()
        yield s


def article(source_id, n, titre="Titre", publie=datetime(2026, 5, 4, 8, 0), collecte=MAINTENANT):
    return ArticlesPropres(
        source_id=source_id,
        url=f"http://x/{source_id}/{n}",
        guid=f"{source_id}-{n}",
        title=titre,
        description="",
        published_at=publie,
        date_source="pubDate",
        collecte_le=collecte,
        fichier_brut="f.json",
    )


def rejet(source_id, n, collecte=MAINTENANT):
    return Rejets(
        source_id=source_id,
        url=f"http://x/{source_id}/r{n}",
        title="Titre",
        regle="R00_invalide",
        collecte_le=collecte,
        fichier_brut="f.json",
    )


def test_evaluer_tout_ok():
    controles = evaluer(faits({"a": {"gardes": 5, "rejetes": 1}}))
    assert [c["nom"] for c in controles] == [
        "aucune_date_future",
        "aucun_titre_vide",
        "taux_rejet_par_source",
    ]
    assert all(c["ok"] for c in controles)


def test_evaluer_date_future_en_echec():
    c = par_nom(evaluer(faits(dates_futures=2)))["aucune_date_future"]
    assert not c["ok"]
    assert c["valeur"] == 2
    assert "2" in c["message"]


def test_evaluer_titre_vide_en_echec():
    c = par_nom(evaluer(faits(titres_vides=1)))["aucun_titre_vide"]
    assert not c["ok"]
    assert c["valeur"] == 1


def test_evaluer_taux_en_echec_nomme_la_source():
    c = par_nom(
        evaluer(faits({"a": {"gardes": 1, "rejetes": 9}, "b": {"gardes": 9, "rejetes": 1}}))
    )
    c = c["taux_rejet_par_source"]
    assert not c["ok"]
    assert c["valeur"] == pytest.approx(0.9)
    assert "a (90%)" in c["message"]
    assert "b (" not in c["message"]


def test_evaluer_taux_a_80_pourcent_passe():
    c = par_nom(evaluer(faits({"a": {"gardes": 2, "rejetes": 8}})))["taux_rejet_par_source"]
    assert c["ok"]


def test_evaluer_taux_a_81_pourcent_echoue():
    c = par_nom(evaluer(faits({"a": {"gardes": 19, "rejetes": 81}})))["taux_rejet_par_source"]
    assert not c["ok"]


def test_evaluer_source_sans_entree_ignoree():
    c = par_nom(evaluer(faits({"a": {"gardes": 0, "rejetes": 0}})))["taux_rejet_par_source"]
    assert c["ok"]
    assert c["valeur"] == 0.0


def test_collecter_faits_compte_sur_le_jour(session):
    veille = datetime(2026, 5, 3, 23, 0)
    session.add_all(
        [
            article("a", 1),
            article("a", 2, publie=datetime(2026, 5, 4, 14, 0)),
            article("a", 3, publie=datetime(2026, 5, 4, 13, 0)),
            article("a", 4, titre="   "),
            article("b", 5),
            # autre jour : ne compte pas
            article("b", 6, titre=" ", publie=datetime(2026, 5, 10), collecte=veille),
            rejet("a", 1),
            rejet("b", 2),
            rejet("b", 3, collecte=veille),
        ]
    )
    session.commit()
    resultat = collecter_faits(session, JOUR, MAINTENANT)
    assert resultat["par_source"] == {
        "a": {"gardes": 4, "rejetes": 1},
        "b": {"gardes": 1, "rejetes": 1},
    }
    # 14h est au dela de la tolerance d'une heure, 13h pile non
    assert resultat["dates_futures"] == 1
    assert resultat["titres_vides"] == 1


def test_executer_renvoie_des_metriques_plates(session):
    session.add_all([article("a", 1), rejet("a", 1), rejet("a", 2), rejet("a", 3)])
    session.commit()
    resultat = executer(session, JOUR, MAINTENANT)
    assert resultat["ok"]
    assert resultat["metriques"] == {
        "dates_futures": 0,
        "titres_vides": 0,
        "taux_rejet_max": pytest.approx(0.75),
    }


def test_main_sort_en_code_1_si_echec(monkeypatch):
    monkeypatch.setattr(controles_qualite, "ouvrir_session", lambda: Session())
    monkeypatch.setattr(
        controles_qualite,
        "executer",
        lambda *args: {
            "ok": False,
            "controles": [{"nom": "aucun_titre_vide", "ok": False, "valeur": 1, "message": "1"}],
            "metriques": {},
        },
    )
    with pytest.raises(SystemExit) as sortie:
        controles_qualite.main()
    assert sortie.value.code == 1


def test_main_ne_sort_pas_si_tout_est_ok(monkeypatch):
    monkeypatch.setattr(controles_qualite, "ouvrir_session", lambda: Session())
    monkeypatch.setattr(
        controles_qualite,
        "executer",
        lambda *args: {"ok": True, "controles": [], "metriques": {}},
    )
    controles_qualite.main()
