# Qualité des données : règles de nettoyage

Le nettoyage lit les flux RSS bruts et sépare les articles gardés (table `articles_propres`) des articles écartés (table `rejets`, avec le motif dans `regle`). Les règles vivent dans trois modules :

- `nettoyage_rss.py` : validité de la donnée (R00)
- `regles.py` : règles éditoriales (liste `REGLES`)
- `dedoublonnage.py` : doublons (R10, R11)

La première règle qui s'applique donne le motif de rejet. L'ordre ci-dessous suit le code. Les chiffres et exemples viennent de la base réelle, collectes du 2026-11-12 (de 10h59 à 15h30).

## R00_invalide

- Ce qu'elle écarte : un item dont le titre ou le lien est vide.
- Pourquoi : sans titre ou sans lien, l'article n'est ni lisible ni identifiable, il ne peut pas servir de clé.
- Exemple réel : 0 occurrence observée dans les rejets.

## R00_trop_vieux

- Ce qu'elle écarte : un item publié plus de 24 h avant la collecte (`MAX_AGE`).
- Pourquoi : les flux RSS renvoient parfois des archives ; on ne veut que l'actualité du jour.
- Exemple réel : 230 rejets sur 9 sources. Titre : "Colère lycéenne : Plainte, suspects, Macron... Le point sur la bouteille d'essence jetée sur" (20minutes_idf, collecte du 2026-11-12, `xml/2026-11-12/20261112T105913704324Z_20minutes_idf.xml`).

## R00_date_future

- Ce qu'elle écarte : un item daté de plus d'une heure après la collecte (`TOLERANCE_FUTUR`).
- Pourquoi : une date dans le futur est une erreur de flux ; la tolérance d'une heure absorbe les décalages d'horloge.
- Exemple réel : 1 rejet. Titre : "Les entreprises sont incitées à mal faire : Julia Faure et Guillaume Declair balancent" (le_parisien, collecte du 2026-11-12, `xml/2026-11-12/20261112T105931393230Z_le_parisien.xml`; titre normalisé pour la typographie).

## R01_horoscope

- Ce qu'elle écarte : un titre contenant le mot "horoscope" (mot entier, sans tenir compte de la casse).
- Pourquoi : contenu récurrent sans valeur d'information, qui pollue les analyses de sujets.
- Exemple réel : 1 rejet. Titre : "L'horoscope de Rob Brezsny pour la semaine du 12 au 18 novembre 2026" (courrier_international, collecte du 2026-11-12, `xml/2026-11-12/20261112T105919628937Z_courrier_international.xml`; titre normalisé pour la typographie).

## R02_audiences_tv

- Ce qu'elle écarte : un titre qui commence par "Audience TV" ou "Audiences TV".
- Pourquoi : les articles de résultats d'audience sont du bruit télévisuel, hors du périmètre de l'actualité suivie.
- Exemple réel : 1 rejet. Titre : "Audiences TV : la série Les Disparus des Argonnes dépassée par..." (le_parisien, collecte du 2026-11-12, `xml/2026-11-12/20261112T105931393230Z_le_parisien.xml`; titre normalisé pour la typographie).

## R10_doublon_exact

- Ce qu'elle écarte : un article dont l'URL a déjà été gardée.
- Pourquoi : les flux se recouvrent d'une collecte à l'autre ; sans cette règle, un même article serait compté plusieurs fois.
- Exemple réel : 474 rejets sur 10 sources, dont 155 pour le_parisien. Titre : "Paris : Des voleurs d'or séquestrent des enfants pour des bijoux" (20minutes_idf, collecte du 2026-11-12, `xml/2026-11-12/20261112T120002716069Z_20minutes_idf.xml`).

## R11_doublon_approx

- Ce qu'elle écarte : un article dont le titre est trop proche d'un article déjà gardé. Similarité de Jaccard sur les mots du titre (minuscules, sans accents, mots d'au moins 3 lettres), seuil `SEUIL_JACCARD` = 0.85.
- Pourquoi : une même dépêche est reprise par plusieurs médias avec de légères variations de titre, y compris entre sources différentes.
- Exemple réel : 1 rejet. Titre écarté : "RN : Bardella a porté plainte pour faux et usage de faux après les accusations d'antisémitisme" (la_croix, collecte du 2026-11-12 à 12h30, `xml/2026-11-12/20261112T123012078334Z_la_croix.xml`). Titre gardé le plus proche : "Jordan Bardella a porté plainte pour faux et usage de faux après les accusations d'antisémitisme" (le_figaro, collecte de 12h00). Similarité calculée : 0.91.

## Les dix pollueurs observés

| N | Pollueur | Volume | Sources | Exemple | Règle |
|---|----------|--------|---------|---------|-------|
| 1 | Doublons exacts | 474 | 10 | "Paris : Des voleurs d'or séquestrent des enfants pour des bijoux" (20minutes_idf) | R10_doublon_exact |
| 2 | Articles trop anciens | 230 | 9 (l_express 83, l_actualite 48, paris_match 25, la_croix 19, ars_idf 19, 20minutes_idf 18, le_figaro 9, franceinfo 7, le_monde 2) | "Colère lycéenne : Plainte, suspects, Macron..." (20minutes_idf) | R00_trop_vieux |
| 3 | Date reconstruite depuis l'URL (pubDate absente) | 163 articles gardés | 1 (le_parisien) | articles du le_parisien, `date_source` = url | non couvert, la date est reconstruite, l'article est gardé |
| 4 | Date de collecte utilisée par défaut | 1 article gardé | 1 (le_parisien) | "8 euros l'assiette à la cantine : ces étudiants Erasmus racontent" | non couvert, la date est celle de la collecte |
| 5 | Doublons approximatifs | 1 | 1 (la_croix) | "RN : Bardella a porté plainte pour faux et usage de faux..." | R11_doublon_approx |
| 6 | Dates futures | 1 | 1 (le_parisien) | "Les entreprises sont incitées à mal faire..." | R00_date_future |
| 7 | Horoscope | 1 | 1 (courrier_international) | "L'horoscope de Rob Brezsny pour la semaine du 12 au 18 novembre 2026" | R01_horoscope |
| 8 | Audiences et programmes TV | 1 | 1 (le_parisien) | "Audiences TV : la série Les Disparus des Argonnes..." (aucun programme TV proprement dit : 0 occurrence observée) | R02_audiences_tv |
| 9 | Publi-reportages et contenus sponsorisés | 0 occurrence observée | 0 | aucun | non couvert |
| 10 | Jeux et concours | 0 occurrence observée | 0 | aucun | non couvert |

Autres familles recherchées, 0 occurrence observée à la date du 2026-11-12 : dépêches d'agence (AFP, Reuters), titres vides, encodages cassés (caractères "Ã" ou "Â" parasites), titres contenant "horoscope" restés dans les articles gardés.
