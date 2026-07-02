# Backend conventions

## Formatting — REQUIRED before every commit / merge to `main`

All Python under `backend/` MUST be Black-formatted at line length **120**.
The line length is pinned in `backend/pyproject.toml` (`[tool.black] line-length = 120`),
so the flag is implicit — just run Black on the tree:

```sh
backend/.venv/bin/python -m black backend/
```

Gate (must exit 0 before any commit or merge to `main`):

```sh
backend/.venv/bin/python -m black --check backend/
```

Never commit or merge code that `black --check` would reformat. If `black` is not
installed in the venv: `backend/.venv/bin/python -m pip install black`.
