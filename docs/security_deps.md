# Dependency audit

`pip-audit` (CI job `audit`, report only) lists known advisories for the pinned runtime packages. Result on 2026-10-19 for `requirements-audit.txt`
(the exact pins of `requirements-base.txt`):

| Package | Pinned | Fixed in | Note |
|---------|--------|----------|------|
| requests | 2.34.2 (was 2.32.5) | 2.33.0 | bumped 2026-10-20 |
| python-dotenv | 1.2.4 (was 1.1.1) | 1.2.2 | bumped 2026-10-20 |
| pillow | 12.3.0 (was 12.1.1) | 12.3.0 | bumped 2026-10-20 |
| anyio | 4.3.0 | 4.14.2 | pinned on purpose: shazamio 0.6.0 needs `anyio==4.3.0` |
| torch | 2.11.0 | 2.13.0 | pinned with numpy 1.26.4 and sherpa-onnx |

Transitive packages in the development environment also have advisories (urllib3, aiohttp, transformers, nltk, lxml, setuptools and others);
they are not pinned by the project and move with the direct ones.

`requests`, `python-dotenv` and `pillow` were bumped (pytest green); the packaged build still has to be rebuilt and started. `torch` and `anyio` were not touched: each changes the build (PyInstaller, numpy and torch constraints) and needs a full `build.bat` and a manual run.
Suggested order: `requests`, `python-dotenv`, `pillow` first (small, no ABI coupling), then `torch`/`anyio` together with the shazamio and numpy pins.
After each bump: `python -m pytest`, `pip-audit`, a build, and a start of the packaged app.
