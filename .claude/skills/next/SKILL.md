---
description: (Sonnet) Traite la prochaine tâche non cochée de todo.md avec le cycle explore → plan → implémente → vérifie → review → commit. À lancer manuellement, une tâche par invocation.
disable-model-invocation: true
model: sonnet
effort: medium
allowed-tools: Bash(pytest *) Bash(ruff *) Bash(python -m pytest *) Bash(python -m ruff *) Bash(.venv/Scripts/python *) Bash(git status *) Bash(git diff *) Bash(git log *)
---

Traite la prochaine tâche non cochée de `todo.md`. Une seule tâche. Ne passe jamais une étape marquée [STOP] sans mon accord explicite.

## 1. EXPLORE

- Lis `todo.md`, cite la première tâche non cochée (son id et son texte).
- **Si la tâche porte le tag `[opus]`, arrête-toi ici** et réponds uniquement : « Tâche <id> taguée [opus] : lance `/next-hard` ». Ne fais rien d'autre.
- Lis les sections de `docs/spec-technique.md` que la tâche concerne. Cite-les en une ligne.
- Si la tâche touche du code existant que tu n'as pas lu dans cette session, lis-le et résume en 3 lignes.
- Si les fixtures sont concernées, lis `tests/fixtures/reference_charts.json` (`_meta` + le premier thème suffit pour comprendre la forme).

## 2. PLAN [STOP]

- Étapes, fichiers créés/modifiés, tests à écrire (avec les valeurs de fixture visées et la tolérance).
- Aucun code. Attends ma validation.

## 3. IMPLEMENT

- Implémente le plan validé. Écris les tests **avant ou en même temps** que le code.
- Interdit : modifier une valeur attendue dans les fixtures, élargir une tolérance, `skip` un test.

## 4. VÉRIFICATION

- `ruff check . && ruff format --check .` puis `pytest -q`. Montre la sortie exacte.
- Si ça échoue, corrige et relance. Si tu tournes en rond après 3 essais, arrête et explique-moi ce qui coince.

## 5. REVIEW [STOP]

- `git diff --stat` puis le diff complet.
- Si la tâche touche `main.py`, la validation d'entrées, ou l'auth par clé : lance `/security-review`.
- Attends ma validation.

## 6. COMMIT

- Message : impératif, une ligne ≤ 72 caractères, préfixé par l'id de tâche (`E04: add local→UT conversion with DST detection`).
- Coche la case dans `todo.md` dans le même commit.
