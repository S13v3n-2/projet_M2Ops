from la_gazette_des_sorciers.dedoublonnage import (
    Dedoublonneur,
    dedoublonner,
    jaccard,
    mots_du_titre,
)


def art(titre, url, source="a"):
    return {"title": titre, "url": url, "source_id": source}


def test_mots_du_titre_sans_accents_ni_mots_courts():
    assert mots_du_titre("L’État a décidé de réagir !") == frozenset({"etat", "decide", "reagir"})


def test_jaccard():
    a, b = mots_du_titre("le prix du pain augmente"), mots_du_titre("prix du pain en hausse")
    # mots retenus : {prix, pain, augmente} et {prix, pain, hausse} -> 2 communs sur 4
    assert jaccard(a, b) == 0.5
    assert jaccard(a, frozenset()) == 0.0
    assert jaccard(a, a) == 1.0


def test_doublon_exact_sur_l_url():
    gardes, doublons = dedoublonner([art("Titre un", "u1"), art("Tout autre sujet ici", "u1")])
    assert len(gardes) == 1
    assert doublons[0]["regle"] == "R10_doublon_exact"


def test_doublon_approximatif_garde_le_premier():
    premier = art("Violences du 17 octobre : le gouvernement sous pression", "u1", "a")
    copie = art("Violences du 17 octobre : le gouvernement sous pression !", "u2", "b")
    autre = art("Le Sénat adopte le budget après un long débat", "u3", "b")
    gardes, doublons = dedoublonner([premier, copie, autre])
    assert [g["url"] for g in gardes] == ["u1", "u3"]
    assert doublons[0]["regle"] == "R11_doublon_approx"
    assert doublons[0]["doublon_de"] == "u1"


def test_titres_differents_ne_sont_pas_des_doublons():
    gardes, doublons = dedoublonner(
        [
            art("Carburants en Essonne : où faire le plein", "u1"),
            art("Match PSG Barça ce soir", "u2"),
        ]
    )
    assert len(gardes) == 2
    assert doublons == []


def test_l_etat_est_conserve_entre_les_appels():
    d = Dedoublonneur()
    d.filtrer([art("Titre identique pour deux flux", "u1", "a")])
    gardes, doublons = d.filtrer([art("Titre identique pour deux flux", "u2", "b")])
    assert gardes == []
    assert doublons[0]["doublon_de"] == "u1"
