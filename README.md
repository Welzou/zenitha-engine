# zenitha-engine

Microservice de calcul d'astrocartographie sidérale. Il reçoit un instant et un
lieu de naissance, et renvoie les positions sidérales de 12 corps ainsi que 48
lignes astrocartographiques (MC/IC/AC/DC) en GeoJSON.

Le service est **sans état** : il ne connaît ni les villes, ni les critères,
ni les utilisateurs.

Calcul via [pyswisseph](https://pypi.org/project/pyswisseph/) (Swiss
Ephemeris) en mode Moshier — pas de fichiers d'éphémérides `.se1` à
télécharger, précision suffisante pour l'astrocartographie.

## Licence

AGPL-3.0 (voir [`LICENSE`](LICENSE)). Ce choix n'est pas arbitraire :
pyswisseph est lui-même publié sous AGPL-3.0 (ou licence commerciale Astrodienst),
et cette licence impose de publier le code de tout service réseau qui l'utilise.

## Lancer le service

Développé sur Windows natif (Git Bash), déployé sur Linux. Python 3.11
requis (`pyswisseph` n'a pas de wheel précompilée au-delà de 3.11).

```bash
python -m venv .venv
source .venv/Scripts/activate      # Git Bash, Windows
pip install -e ".[dev]"
uvicorn app.main:app --port 8001 --reload
```

Tests et lint :

```bash
pytest -q
ruff check . && ruff format .
```

Si `pytest`, `ruff` ou `uvicorn` sont introuvables alors que le venv est
activé, utiliser la forme explicite : `.venv/Scripts/python -m pytest -q`.

## API

### `GET /health`

```bash
curl http://localhost:8001/health
```

```json
{"status": "ok", "swisseph": "2.10.03", "pyswisseph": "2.10.3.2", "tzdata": "2026a"}
```

### `POST /v1/chart`

```bash
curl -X POST http://localhost:8001/v1/chart \
  -H "Content-Type: application/json" \
  -H "X-Engine-Key: $ENGINE_API_KEY" \
  -d '{
        "date": "2000-01-01",
        "time": "12:00",
        "lat": 48.8566,
        "lng": 2.3522,
        "ayanamsa": "fagan_bradley",
        "fold": null,
        "lat_step_deg": 0.5
      }'
```

Renvoie l'instant résolu (UTC, fuseau IANA, jour julien), la valeur de
l'ayanamsa, les 12 positions sidérales et les 48 lignes en GeoJSON
(`MultiLineString`, coordonnées `[lng, lat]`).

Le header `X-Engine-Key` n'est vérifié que si la variable d'environnement
`ENGINE_API_KEY` est définie côté serveur.
