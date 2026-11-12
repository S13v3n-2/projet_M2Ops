from collections import Counter
from datetime import date
from pathlib import Path

NB_EXEMPLES = 3
NB_TOP = 5


def construire_rapport(resultats: list[dict]) -> dict:
    """resultats : un dict par flux nettoyé, {"source_id", "entres", "gardes", "rejets"}."""
    par_source: dict[str, dict] = {}
    par_regle: Counter = Counter()
    par_regle_et_source: Counter = Counter()
    exemples: dict[str, list[str]] = {}

    for r in resultats:
        source = par_source.setdefault(r["source_id"], {"entres": 0, "gardes": 0, "rejetes": 0})
        source["entres"] += r["entres"]
        source["gardes"] += r["gardes"]
        source["rejetes"] += len(r["rejets"])
        for rejet in r["rejets"]:
            par_regle[rejet["regle"]] += 1
            par_regle_et_source[(rejet["regle"], r["source_id"])] += 1
            titres = exemples.setdefault(rejet["regle"], [])
            if len(titres) < NB_EXEMPLES:
                titres.append(rejet["title"])

    for source in par_source.values():
        source["taux_rejet"] = source["rejetes"] / source["entres"] if source["entres"] else 0.0

    entres = sum(s["entres"] for s in par_source.values())
    gardes = sum(s["gardes"] for s in par_source.values())
    return {
        "entres": entres,
        "gardes": gardes,
        "rejetes": entres - gardes,
        "par_regle": dict(par_regle.most_common()),
        "par_source": par_source,
        "top_rejets": [
            {"regle": regle, "source": source, "nombre": nombre}
            for (regle, source), nombre in par_regle_et_source.most_common(NB_TOP)
        ],
        "exemples": exemples,
    }


def rapport_en_markdown(rapport: dict, jour: date) -> str:
    lignes = [
        f"# Rapport de qualité — {jour.isoformat()}",
        "",
        f"- Entrés : **{rapport['entres']}**",
        f"- Gardés : **{rapport['gardes']}**",
        f"- Rejetés : **{rapport['rejetes']}**",
        "",
        "## Rejets par règle",
        "",
        "| Règle | Rejetés | Exemples |",
        "| --- | ---: | --- |",
    ]
    for regle, nombre in rapport["par_regle"].items():
        exemples = " ; ".join(rapport["exemples"].get(regle, []))
        lignes.append(f"| {regle} | {nombre} | {exemples} |")

    lignes += ["", "## Par source", "", "| Source | Entrés | Gardés | Rejetés | Taux de rejet |"]
    lignes.append("| --- | ---: | ---: | ---: | ---: |")
    for nom, s in sorted(rapport["par_source"].items()):
        lignes.append(
            f"| {nom} | {s['entres']} | {s['gardes']} | {s['rejetes']} | {s['taux_rejet']:.0%} |"
        )

    lignes += ["", f"## Les {NB_TOP} rejets les plus fréquents (règle, source)", ""]
    for t in rapport["top_rejets"]:
        lignes.append(f"- {t['regle']} — {t['source']} : {t['nombre']}")
    return "\n".join(lignes) + "\n"


def ecrire_rapport(rapport: dict, jour: date, dossier: Path) -> Path:
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / f"qualite-{jour.isoformat()}.md"
    chemin.write_text(rapport_en_markdown(rapport, jour), encoding="utf-8")
    return chemin
