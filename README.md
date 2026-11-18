# Face-Recognition Performance Lab

A local, single-machine web application for an academic study of face-verification
performance. It enrols consenting participants, runs 1:1 verification trials from a
webcam, logs every trial with ground truth and condition tags, and computes
**FAR, FRR, GAR, decision accuracy, and EER** with a threshold sweep and confidence
intervals. Results export as CSV without any biometric content. Consent, withdrawal,
retention, and a tamper-evident audit trail are built in.

> **Scope.** This is a learning and measurement tool, not a security product. It makes
> no claim of robustness against presentation attacks beyond what the optional liveness
> module measures. See [`docs/`](docs/) for the full specification.

## Documentation

The complete specification lives in [`docs/`](docs/):

- [PRD.md](docs/PRD.md) — requirements (FR / NFR)
- [USE_CASES.md](docs/USE_CASES.md) — use cases (UC)
- [FEATURES.md](docs/FEATURES.md) — feature list (F)
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — layers, components, interfaces
- [SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md) — data model, API, metrics, tests
- [IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) — milestones, checklist, risks

## Quick start

```bash
# 1. Create and activate a virtual environment (Python 3.11 or 3.12)
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux / macOS

# 2. Install (core + dev tools). Add the real face model separately: pip install -e ".[engine]"
pip install -e ".[dev]"

# 3. Run the tests (no webcam or model needed — uses a deterministic fake engine)
pytest

# 4. Create the database and the first admin account
alembic upgrade head
python -m biometric_lab.scripts.create_admin --username admin

# 5. Run the app (binds to 127.0.0.1 only)
uvicorn biometric_lab.main:app --host 127.0.0.1 --port 8000
```

Then open <http://127.0.0.1:8000> in a Chromium-based browser.

## Face model

The identity engine is pluggable (see `core/face/`):

- **Primary:** InsightFace (`buffalo_l`). Install with `pip install -e ".[engine]"`.
- **Fallback:** OpenCV Zoo YuNet + SFace, if InsightFace will not install on Windows.
- **Tests:** a deterministic `FakeFaceEngine`, so the full suite runs with no model download.

InsightFace pretrained weights are for **non-commercial research use**; see
`docs/model_licences.md` once the engine is set up.

## Privacy and keys

- Templates are stored as **encrypted embeddings only** — raw frames are never persisted.
- The encryption key lives in a file **outside** `data/`, pointed to by `BIOMETRIC_LAB_KEY_FILE`.
  Losing it makes templates unreadable; re-enrolment is the recovery path.
- The app binds to `127.0.0.1` and makes no outbound network calls at runtime.

## Status

Under active construction from the specification in `docs/`. See
[IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) for milestone progress.

## Licence

MIT for the application code. Face-model weights carry their own licences — see
`docs/model_licences.md`.
