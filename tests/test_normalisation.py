from la_gazette_des_sorciers.normalisation import (
    borner_extrait,
    decoder_entites,
    nettoyer,
    normaliser_espaces,
    reparer_encodage,
    retirer_html,
)


def test_retirer_html():
    assert retirer_html("<p>Bonjour <b>le monde</b></p>").split() == ["Bonjour", "le", "monde"]
    assert retirer_html("sans balise") == "sans balise"


def test_decoder_entites():
    assert (
        decoder_entites("Rock &amp; roll &eacute;t&eacute; &#39;ok&#39;") == "Rock & roll été 'ok'"
    )


def test_reparer_encodage():
    # "à" cassé = "Ã" + espace insécable
    assert reparer_encodage("Ã©tÃ© Ã\xa0 Paris") == "été à Paris"
    assert reparer_encodage("Lâ€™Ã©tÃ©") == "L’été"
    # un texte correct n'est pas touché
    assert reparer_encodage("L’été à Paris") == "L’été à Paris"
    # un texte qui ressemble à un défaut mais ne se décode pas reste inchangé
    assert reparer_encodage("Ã seul") == "Ã seul"


def test_normaliser_espaces():
    assert normaliser_espaces("  un \n  deux\t trois  ") == "un deux trois"


def test_borner_extrait():
    assert borner_extrait("court") == "court"
    long = "mot " * 100
    resultat = borner_extrait(long, maximum=50)
    assert len(resultat) <= 50
    assert resultat.endswith("…")
    assert "mo…" not in resultat  # coupé à la fin d'un mot


def test_nettoyer_enchaine_les_transformations():
    assert nettoyer("<p>L&#39;Ã©tÃ©   dernier</p>") == "L'été dernier"


def casser(texte):
    # ce que donne un flux UTF-8 lu à tort en cp1252
    return texte.encode("utf-8").decode("cp1252")


def test_reparer_encodage_sur_des_titres_reels():
    titres = [
        "« Everytime » : la critique d'un film magnifique sur un deuil impossible",
        "Colère lycéenne : Plainte, suspects, Macron… Le point sur l’affaire",
        "L’horoscope de Rob Brezsny pour la semaine du 12 au 18 novembre 2026",
        "Prix des carburants en Île-de-France : où faire le plein ?",
    ]
    for titre in titres:
        assert casser(titre) != titre
        assert reparer_encodage(casser(titre)) == titre
        assert reparer_encodage(titre) == titre
