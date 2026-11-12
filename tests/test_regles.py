from la_gazette_des_sorciers.regles import (
    appliquer_regles,
    est_audiences_tv,
    est_horoscope,
)


def article(titre):
    return {"title": titre}


def test_horoscope():
    assert est_horoscope(article("L’horoscope de Rob Brezsny pour la semaine du 12 au 18 novembre"))
    assert est_horoscope(article("HOROSCOPE du jour"))
    assert not est_horoscope(article("Le Sénat examine le budget"))


def test_audiences_tv():
    assert est_audiences_tv(article("Audiences TV : la série dépassée par un autre programme"))
    assert est_audiences_tv(article("Audience TV : record pour la finale"))
    # le mot "audiences" ailleurs dans le titre ne doit pas déclencher la règle
    assert not est_audiences_tv(article("Le procès reprend, audiences TV filmées interdites"))


def test_appliquer_regles_renvoie_l_identifiant():
    assert appliquer_regles(article("Horoscope de la semaine")) == "R01_horoscope"
    assert appliquer_regles(article("Audiences TV : le classement")) == "R02_audiences_tv"
    assert appliquer_regles(article("Un article d'actualité")) is None
