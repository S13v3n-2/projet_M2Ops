# Contrat de données

Le brut collecté (flux XML et métadonnées JSON) est déposé dans le bucket S3 gazette-bronze. Les données nettoyées et les rejets sont stockés dans PostgreSQL. Le détail des règles de qualité est dans docs/qualite.md.

## Schéma

Types relevés dans la migration alembic et dans db_models.py. Toutes les dates sont en UTC, sans fuseau (DateTime naïf).

### sources

| Colonne | Type SQL | Nul | Rôle |
|---------|----------|-----|------|
| id | VARCHAR (clé primaire) | non | identifiant de la source |
| name | VARCHAR | non | nom de la source |
| type | VARCHAR | non | type de source |
| region | VARCHAR | non | région couverte |
| url_flux | VARCHAR | non | adresse du flux RSS |
| conditions | VARCHAR | non | conditions d'utilisation |
| notes | VARCHAR | non | remarques |
| actif | BOOLEAN | non | source collectée ou non |
| derniere_reussite | TIMESTAMP | oui | dernière collecte réussie |
| echecs_consecutifs | INTEGER | oui | nombre d'échecs de suite |
| etag | VARCHAR | oui | ETag du dernier flux |
| last_modified | TIMESTAMP | oui | Last-Modified du dernier flux |

### articles_propres

| Colonne | Type SQL | Nul | Rôle |
|---------|----------|-----|------|
| id | INTEGER (clé primaire) | non | identifiant technique |
| source_id | VARCHAR | non | source de l'article (clé étrangère vers sources.id) |
| url | VARCHAR | non | lien de l'article (unique) |
| guid | VARCHAR | non | identifiant de l'item dans le flux |
| title | VARCHAR | non | titre |
| description | VARCHAR | non | extrait court, 300 caractères au plus |
| published_at | TIMESTAMP | non | date de publication retenue |
| date_source | VARCHAR | non | origine de la date : pubDate, url ou collecte |
| collecte_le | TIMESTAMP | non | date de collecte du brut |
| fichier_brut | VARCHAR | non | clé de l'objet brut dans le bucket |

Contrainte : url unique.

date_source indique d'où vient published_at : pubDate (date du flux), url (date lue dans l'adresse de l'article) ou collecte (date de collecte, en dernier recours).

### rejets

| Colonne | Type SQL | Nul | Rôle |
|---------|----------|-----|------|
| id | INTEGER (clé primaire) | non | identifiant technique |
| source_id | VARCHAR | non | source de l'item (clé étrangère vers sources.id) |
| url | VARCHAR | non | lien de l'item rejeté |
| title | VARCHAR | non | titre |
| regle | VARCHAR | non | règle de qualité qui a rejeté l'item |
| collecte_le | TIMESTAMP | non | date de collecte du brut |
| fichier_brut | VARCHAR | non | clé de l'objet brut dans le bucket |

Contraintes : unique sur (url, regle), index ix_rejets_regle sur regle.

## Fraîcheur attendue

- La gazette doit être disponible à 7h du matin (cadrage).
- Elle couvre les 24 dernières heures : un article plus vieux que 24 h est rejeté (MAX_AGE dans nettoyage_rss.py).
- Une date future est tolérée jusqu'à 1 h (TOLERANCE_FUTUR), au-delà l'item est rejeté.
- La collecte tourne toutes les 30 minutes (cron "0,30 * * * *" du flow gazette_download_article) et le nettoyage se déclenche à la fin d'une collecte réussie (flow gazette_clear_article).

## Ce qu'on ne stocke pas

En base, on garde seulement : titre, extrait court (300 caractères au plus, voir borner_extrait), lien, date et source.

Ne sont pas stockés : texte intégral des articles, images, noms d'auteurs, commentaires, adresses e-mail, identifiants de lecteurs, cookies, et plus généralement toute donnée personnelle. Le flux brut conservé dans le bucket est celui publié par la source.

## Traçabilité

Chaîne : article propre, puis fichier_brut (objet XML du bucket), puis source (source_id vers sources).

- fichier_brut contient la clé de l'objet XML brut, de la forme xml/AAAA-MM-JJ/horodatage_source.xml.
- Les métadonnées de la collecte sont dans l'objet JSON de même nom sous json/ (ici json/2026-11-12/20261112T105913704324Z_20minutes_idf.json). Ce JSON porte la clé du XML dans son champ s3_key.
- source_id renvoie à la ligne de sources (adresse du flux, conditions).

Exemple vérifié sur une ligne réelle :

```sql
SELECT a.url, a.fichier_brut, s.name, s.url_flux
FROM articles_propres a
JOIN sources s ON s.id = a.source_id
LIMIT 1;
```

Résultat : source 20minutes_idf, fichier_brut xml/2026-11-12/20261112T105913704324Z_20minutes_idf.xml.

Même principe pour les rejets : rejets.fichier_brut pointe vers le XML brut, rejets.regle donne la règle appliquée.

Limites constatées : fichier_brut référence le XML mais pas le JSON (le lien vers le JSON se déduit du nom, même jour et même horodatage). Aucun lien n'est stocké vers la position de l'item dans le flux brut ; on retrouve l'item par son url ou son guid dans le XML.

## Rétention

Règle de conservation retenue, décrite ici. Elle n'est pas appliquée automatiquement à ce stade : aucun mécanisme (règle de cycle de vie du bucket, script de purge) ne la met en oeuvre.

- Brut : les objets du bucket gazette-bronze (préfixes xml/ et json/) sont conservés 90 jours.
- Éditions : les éditions (articles_propres et rapports de qualité) de plus d'un mois sont déplacées vers un stockage froid.
