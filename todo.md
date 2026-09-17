# todo — zenitha-engine

Une case = une tâche implémentable et commitable seule, 30 min à 2 h. Ordre imposé. `/next` (Sonnet) prend la première case non cochée ; si elle porte `[opus]`, il s'arrête et tu lances `/next-hard` (Opus) à la place.

## Bloc 1 — Squelette

- [x] E01 Scaffold : `pyproject.toml` avec `requires-python = ">=3.11"` (fastapi, uvicorn, pydantic v2, pyswisseph, timezonefinder, tzdata ; dev : pytest, httpx, ruff), `app/__init__.py`, `app/main.py` avec `GET /health` renvoyant versions de swisseph et tzdata. `pip install -e ".[dev]"` doit passer sans compiler (wheel pyswisseph 3.11 Windows). `pytest` vert avec un test de health.
- [ ] E02 `app/bodies.py` : constantes des 11 corps calculés + Ketu dérivé, mapping ayanamsa id → `swe.SIDM_*` pour `fagan_bradley`, `lahiri`, `raman`, `krishnamurti`, `true_citra`. Test : chaque id résout vers une constante existante.
- [ ] E03 `app/schemas.py` : `ChartRequest` (date, time, lat, lng, ayanamsa, fold, lat_step_deg avec bornes), `ChartResponse` et sous-modèles (instant, ayanamsa, positions, lines) conformes au contrat d'API. Test : validation des bornes (lat 91 refusé, step 5 refusé).

## Bloc 2 — Temps

- [ ] E04 [opus] `app/timeconv.py` : `resolve_instant(date, time, lat, lng, fold)` → tz IANA, offset, datetime UTC, jd_ut. Erreurs `TZ_NOT_FOUND`, `TIME_AMBIGUOUS` (avec les deux offsets), `TIME_NONEXISTENT`, `DATE_OUT_OF_RANGE` (1800–2199). Tests : les 5 fixtures (tz, offset, utc, jd_ut exacts) + un cas ambigu (Paris 2023-10-29 02:30) + un cas inexistant (Paris 2023-03-26 02:30) + pleine mer.

## Bloc 3 — Positions

- [ ] E05 [opus] `app/positions.py` : `compute_positions(jd_ut, ayanamsa)` → liste de 12 positions (lon sidérale, signe, deg_in_sign, ra, dec, rétrograde) + valeur d'ayanamsa + GST en degrés. Flags `FLG_MOSEPH | FLG_SPEED`, sidéral pour la longitude, `FLG_EQUATORIAL` pour ra/dec. Tests : 5 fixtures, tolérance 0,02° sur lon/ra/dec, 0,001° sur l'ayanamsa ; Ketu = Rahu + 180 exact.

## Bloc 4 — Lignes

- [ ] E06 [opus] `app/lines.py` : `mc_ic_lines(ra, gst)` → deux méridiens de −89° à +89°. Test : `mc_lon` et `ic_lon` des fixtures, tolérance 0,05°.
- [ ] E07 [opus] `app/lines.py` : `ac_dc_lines(ra, dec, gst, step)` → échantillonnage par latitude, `None` quand circumpolaire, découpage en segments à l'antiméridien et aux ruptures. Tests : `acdc_by_lat` des fixtures aux 5 latitudes ; symétrie AC/DC autour de MC ; Tromsø : Soleil sans AC/DC au-delà de la latitude limite ; altitude ≈ 0 recalculée avec `swe.azalt` sur un point AC (tolérance 0,1°).
- [ ] E08 [opus] Assemblage : `build_lines(positions, gst, step)` → 48 objets `{id, body, angle, geometry: MultiLineString}`. Test : 48 lignes, ids uniques, chaque géométrie non vide sauf cas circumpolaire documenté.

## Bloc 5 — API

- [ ] E09 `POST /v1/chart` : enchaîne timeconv → positions → lines, header `X-Engine-Key` vérifié si `ENGINE_API_KEY` défini, mapping des exceptions vers 400 + codes. Tests httpx : réponse complète pour ref01, chaque code d'erreur, 422 sur payload invalide, 401 sans clé.
- [ ] E10 Perf : mesurer `/v1/chart` sur ref01 (cible < 200 ms), ajuster si besoin (pas de recalcul de positions par ligne). Test : assertion de durée large (< 1 s) pour ne pas être flaky.

## Bloc 6 — Qualité et livraison

- [ ] E11 `README.md` : ce que fait le service, licence AGPL et pourquoi, comment lancer, exemple curl. `LICENSE` AGPL-3.0 présent.
- [ ] E12 CI GitHub Actions : ruff + pytest sur push et PR, matrice `ubuntu-latest` + `windows-latest`, Python 3.11.
- [ ] E13 `deploy.sh` + fichier `astro-engine.service` (systemd) tels que décrits dans la spec technique, dans `deploy/`. Ces fichiers tournent sur le VPS Linux, pas ici : shebang `#!/usr/bin/env bash`, LF (garanti par `.gitattributes`), `apt install build-essential python3-dev` dans le script avant `pip install` (pyswisseph compile si le VPS est en 3.12). Pas d'exécution ici, juste les fichiers versionnés.
- [ ] E14 [opus] Revue finale : `/code-review`, `/security-review`, agent `calc-verifier` sur l'API démarrée. Corriger, puis tag `v0.1.0`.

## Hors scope (ne pas faire)

Parans, nœud vrai, fichiers .se1, cache, Docker, auth utilisateur, villes, critères.
