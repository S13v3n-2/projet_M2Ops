import html
import re

# On ne republie qu'un extrait court (voir docs/donnees.md)
MAX_EXTRAIT = 300


def retirer_html(valeur: str) -> str:
    return re.sub(r"<[^>]+>", " ", valeur)


def decoder_entites(valeur: str) -> str:
    return html.unescape(valeur)


def reparer_encodage(valeur: str) -> str:
    """Répare un texte UTF-8 lu à tort en cp1252/latin-1 ("Ã©" -> "é")."""
    if "Ã" not in valeur and "â€" not in valeur:
        return valeur
    for encodage in ("cp1252", "latin-1"):
        try:
            return valeur.encode(encodage).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
    return valeur


def normaliser_espaces(valeur: str) -> str:
    return re.sub(r"\s+", " ", valeur).strip()


def borner_extrait(valeur: str, maximum: int = MAX_EXTRAIT) -> str:
    """Coupe à `maximum` caractères au plus, à la fin d'un mot, et ajoute « … »."""
    if len(valeur) <= maximum:
        return valeur
    coupe = valeur[: maximum - 1]
    if " " in coupe:
        coupe = coupe.rsplit(" ", 1)[0]
    return coupe.rstrip(" ,;:.") + "…"


def nettoyer(valeur: str) -> str:
    """Titre ou extrait propre : sans HTML, sans entités, encodage réparé, espaces nets."""
    return normaliser_espaces(reparer_encodage(decoder_entites(retirer_html(valeur))))
