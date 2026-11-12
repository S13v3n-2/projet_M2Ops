import re
import unicodedata

R10_DOUBLON_EXACT = "R10_doublon_exact"
R11_DOUBLON_APPROX = "R11_doublon_approx"

# Similarité de Jaccard minimale entre deux titres pour les considérer comme doublons.
SEUIL_JACCARD = 0.85


def mots_du_titre(titre: str) -> frozenset[str]:
    # minuscules, sans accents, mots d'au moins 3 lettres (on ignore "de", "le", "la"...)
    sans_accents = unicodedata.normalize("NFKD", titre.lower())
    sans_accents = "".join(c for c in sans_accents if not unicodedata.combining(c))
    return frozenset(m for m in re.findall(r"\w+", sans_accents) if len(m) >= 3)


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


class Dedoublonneur:
    """Garde le premier article de chaque groupe de doublons.

    L'état est conservé entre les appels à `filtrer` : on peut l'appeler flux après flux
    et détecter aussi les doublons entre sources.
    """

    def __init__(self, seuil: float = SEUIL_JACCARD):
        self.seuil = seuil
        self.gardes: list[tuple[dict, frozenset[str]]] = []
        self.urls: set[str] = set()

    def filtrer(self, articles: list[dict]) -> tuple[list[dict], list[dict]]:
        """Renvoie (gardes, doublons). Un doublon reçoit sa règle et `doublon_de` (URL gardée)."""
        gardes, doublons = [], []
        for article in articles:
            if article["url"] in self.urls:
                doublons.append(
                    {**article, "regle": R10_DOUBLON_EXACT, "doublon_de": article["url"]}
                )
                continue
            mots = mots_du_titre(article["title"])
            reference = next(
                (g for g, m in self.gardes if jaccard(mots, m) >= self.seuil),
                None,
            )
            if reference is not None:
                doublons.append(
                    {**article, "regle": R11_DOUBLON_APPROX, "doublon_de": reference["url"]}
                )
                continue
            self.gardes.append((article, mots))
            self.urls.add(article["url"])
            gardes.append(article)
        return gardes, doublons


def dedoublonner(
    articles: list[dict], seuil: float = SEUIL_JACCARD
) -> tuple[list[dict], list[dict]]:
    return Dedoublonneur(seuil).filtrer(articles)
