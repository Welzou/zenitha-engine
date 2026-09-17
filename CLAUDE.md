# zenitha-engine

Microservice de calcul d'astrocartographie sidérale. Python 3.11 (`requires-python >=3.11` ; pas 3.12 : pyswisseph n'a pas de wheel précompilée au-delà de 3.11), FastAPI, pyswisseph (mode Moshier). Public, AGPL-3.0.

Développé sur Windows natif, shell Git Bash. Déployé sur Linux.

Ce service est **sans état** : il reçoit un instant + un lieu de naissance, renvoie positions sidérales et 48 lignes en GeoJSON. Il ne connaît ni les villes, ni les critères, ni les utilisateurs. Tout ça vit dans `zenitha-web`.

## Specs

- `docs/spec-technique.md` — sections « Moteur de calcul », « Contrat d'API », « Stratégie de test ». Source de vérité pour les formules et le JSON d'entrée/sortie.
- `docs/spec-fonctionnelle.md` — section « Règles métier — calcul astro ».
- `tests/fixtures/reference_charts.json` — 5 thèmes de référence avec valeurs attendues et tolérances. **Ne jamais modifier les valeurs attendues pour faire passer un test.**

## Structure

```
app/main.py        FastAPI, routes /health et /v1/chart
app/schemas.py     pydantic v2, entrée/sortie
app/timeconv.py    local → UT (timezonefinder + zoneinfo), erreurs TIME_AMBIGUOUS / TIME_NONEXISTENT
app/positions.py   pyswisseph : longitudes sidérales + RA/dec, ayanamsa
app/lines.py       48 lignes MC/IC/AC/DC, segmentation antiméridien, MultiLineString
app/bodies.py      constantes corps, ayanamsas supportés
tests/             pytest, une classe par module + test_api
```

## Commandes

```bash
python -m venv .venv                          # une fois
source .venv/Scripts/activate                 # à chaque terminal (Git Bash, Windows)
pip install -e ".[dev]"
uvicorn app.main:app --port 8001 --reload     # dev
pytest -q                                     # tests
ruff check . && ruff format .                 # lint + format
```

Le venv est censé être activé dans le terminal qui a lancé Claude Code. Si `pytest`, `ruff` ou `uvicorn` sont introuvables, utiliser la forme explicite `.venv/Scripts/python -m pytest -q` (idem `-m ruff`, `-m uvicorn`) plutôt que d'installer quoi que ce soit en global. Ne jamais toucher au Python système.

## Conventions

- Python typé partout, pydantic v2 pour tout ce qui entre/sort. Pas de `dict` nu dans les signatures.
- `swe.set_sid_mode` appelé par requête, jamais en global mutable partagé.
- Flags Swiss Ephemeris : `FLG_MOSEPH` toujours. Jamais `FLG_SWIEPH` (pas de fichiers .se1).
- Angles en degrés, longitudes ramenées dans ]-180, 180] par `norm180`. Coordonnées GeoJSON en `[lng, lat]`.
- Ketu = Rahu + 180° (longitude et RA), déclinaison opposée. Calculé, jamais appelé séparément.
- Nœud lunaire : `MEAN_NODE`.
- Une erreur métier = exception typée → réponse 400 `{"error": CODE, "detail": ...}`. Codes dans la spec.
- Tests : chaque fonction de calcul est testée contre les fixtures avec les tolérances de `_meta.tolerances`. Un test qui passe en élargissant la tolérance est un test cassé.
- Pas de logs contenant date/heure/lat/lng d'une requête. Loguer la durée et le code de réponse, pas les entrées.

## Règles dures

- Ne jamais commiter `.env`. Les secrets viennent de l'environnement.
- Ne jamais ajouter de dépendance sans la justifier dans le message de commit.
- Ne jamais toucher aux valeurs attendues des fixtures. Si un test échoue, c'est le code qui est faux, sauf preuve documentée dans `_meta.note`.
- Ce repo est public : aucune donnée d'utilisateur réel, aucun exemple avec une vraie personne.
