import re

# Chaque règle prend un article nettoyé (dict) et renvoie True s'il faut l'écarter.
# L'identifiant sert à compter les rejets par règle dans le rapport de qualité.


def est_horoscope(article: dict) -> bool:
    return bool(re.search(r"\bhoroscope\b", article["title"], re.IGNORECASE))


def est_audiences_tv(article: dict) -> bool:
    return bool(re.match(r"\s*audiences? tv\b", article["title"], re.IGNORECASE))


# Ordre = priorité : la première règle qui s'applique donne le motif de rejet.
# Pour désactiver une règle, la commenter ici.
REGLES = [
    ("R01_horoscope", est_horoscope),
    ("R02_audiences_tv", est_audiences_tv),
]


def appliquer_regles(article: dict) -> str | None:
    """Renvoie l'identifiant de la première règle qui écarte l'article, sinon None."""
    for identifiant, regle in REGLES:
        if regle(article):
            return identifiant
    return None
