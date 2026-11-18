# Architecture

**Traces to:** PRD.md (NFR-01, NFR-06, NFR-07, NFR-11), FEATURES.md. **Details:** SYSTEM_DESIGN.md.

---

## 1. Architectural Style

A modular monolith: one Python process serving a FastAPI API and static browser pages, bound to localhost. Layers have one-way dependencies. The face engine, matcher and liveness checker sit behind interfaces so the model can be swapped without touching the rest of the system.

## 2. Context

```
 Operator / Analyst / Admin
          |  browser (Chromium-based, localhost)
          v
 +-------------------------------------------------+
 |  Biometric Lab (single local process)           |
 |   Browser UI  <-- JSON/HTTP 127.0.0.1 -->  API  |
 |                                                 |
 |   Services ---> Core (face, metrics, security)  |
 |        |                                        |
 |        +-----> Database (SQLite, encrypted      |
 |                 templates, hash-chained audit)  |
 +-------------------------------------------------+
          ^                         ^
          |                         |
   Webcam (getUserMedia)     Key file (outside data folder)
```

External systems: none at runtime. The face model is loaded from a local folder (`models/`) after a one-time download, verified by checksum.

## 3. Layers

| Layer | Responsibility | May depend on | Must not |
|---|---|---|---|
| Browser UI (static HTML, JS) | Camera capture, guidance, forms, charts | HTTP API only | Hold templates or keys |
| API (FastAPI routers) | Auth, CSRF, validation, mapping errors to problem responses | Services, schemas | Touch the database or core directly |
| Services | Use-case logic, transactions, audit writes | Core, DB repositories | Know about HTTP |
| Core | Face engine, quality gate, matching, metrics, crypto, redaction | Standard library, numpy, model libraries | Import DB or API; do I/O in metrics |
| DB | Models, repositories, migrations | SQLAlchemy | Contain business rules |

Rules enforced by tests and review:
- `core/metrics` is pure: no I/O, no DB, no HTTP.
- Only services open transactions.
- Image bytes never leave the verification and enrolment services; they are discarded before any response is built.

## 4. Components

| Component | Purpose | Key interface |
|---|---|---|
| Auth | Login, sessions, roles, CSRF, login rate limit | `current_user()`, `require_role(...)` |
| Participants and Consent | Participant registry, consent records, withdrawal | `ParticipantService`, `ConsentService` |
| Enrolment | Capture to quality gate to encrypted templates | `EnrolmentService.enrol(participant, frames)` |
| Verification | 1:1 scoring and decision | `VerificationService.verify(claimed, image, threshold?)` |
| Trials and Runs | Trial recording, ground truth, FTA, run lifecycle | `TrialService.record(run, probe, claimed, image, tags)` |
| Metrics | Rates, intervals, sweep, EER | `core.metrics.*` pure functions; `MetricsService` loads data |
| Export | CSV with metadata and allowlist | `ExportService.trials_csv(run)` |
| Retention and Deletion | Dry-run and live sweeps, anonymise and purge | `RetentionService.sweep(dry_run)` |
| Settings | Typed settings with reason and audit | `SettingsService.set(key, value, reason)` |
| Audit | Hash-chained append and verify | `AuditService.append(event)`, `verify()` |
| Liveness (optional) | Separate checker, separate storage | `LivenessChecker.check(image)` |
| Face engine | Detect, align, embed | `FaceEngine.analyse(image)` |
| Matcher | Score probe against templates | `Matcher.score(probe, templates)` |

## 5. Key Interfaces

```python
class FaceDetection:            # per detected face
    bbox: tuple[float, float, float, float]
    det_score: float
    landmarks: np.ndarray       # (5, 2)
    yaw_deg: float
    embedding: np.ndarray | None  # float32, L2-normalised, shape (dim,)

class ModelInfo(TypedDict):
    detector: str
    recogniser: str
    model_name: str
    model_version: str
    dim: int

class FaceEngine(Protocol):
    info: ModelInfo
    def analyse(self, image_bgr: np.ndarray) -> list[FaceDetection]: ...

class Matcher(Protocol):
    name: str
    def score(self, probe: np.ndarray, templates: Sequence[np.ndarray]) -> float: ...

class LivenessResult(TypedDict):
    method: str
    score: float | None
    passed: bool | None
    reason: str | None

class LivenessChecker(Protocol):
    method: str
    def check(self, image_bgr: np.ndarray) -> LivenessResult: ...
```

Implementations:
- `InsightFaceEngine` (primary) or `YuNetSFaceEngine` (fallback, decided at M0).
- `FakeFaceEngine` (tests): deterministic embeddings from seeded identity and noise.
- `CosineMatcher`: score is the maximum cosine similarity over templates (max fusion).
- `NoLiveness` (returns not run) and an optional passive or active liveness method, chosen at M12.

## 6. Folder Layout

```
biometric system/
  pyproject.toml
  README.md
  .env.example
  .gitignore
  alembic.ini
  docs/                     specification (this pack)
  migrations/versions/      Alembic revisions
  src/biometric_lab/
    main.py                 app factory, middleware, static mount
    config.py               typed settings
    api/                    routers, deps, errors
    schemas/                request and response models
    services/               use-case logic
    core/
      face/                 engine protocol, InsightFace and fallback, fake, quality gate
      matching/             cosine matcher
      metrics/              rates, wilson, sweep, eer (pure)
      liveness/             protocol, none, optional method
      security/             crypto (Fernet), passwords (argon2), csrf
      privacy/              redaction filter, aliases
    db/                     models, session, repositories
    static/                 HTML, js/, css/, vendor/ (Chart.js)
  models/                   (gitignored) model weights with checksums
  data/                     (gitignored) biometric.db, debug/ (if enabled), logs/
  tests/                    unit, integration, model, manual checklist
  scripts/                  create_admin, self_test, verify_audit_chain, make_synthetic_run
```

## 7. Technology Choices

| Concern | Choice | Reason |
|---|---|---|
| Language | Python 3.11 | Mature face-model ecosystem; numpy for metrics. |
| Web framework | FastAPI with pydantic | Typed schemas; automatic validation; simple local serving. |
| Database | SQLite (WAL) via SQLAlchemy 2.x | Single-operator local study; no server to run. |
| Migrations | Alembic | Versioned schema changes (NFR-11). |
| Encryption | `cryptography` Fernet and MultiFernet | Authenticated encryption; key rotation. |
| Passwords | argon2-cffi | Current recommended password hashing. |
| Face model | InsightFace (primary); YuNet and SFace (fallback) | Accuracy and licence status recorded; fallback pip-installable on Windows. |
| Inference runtime | onnxruntime (CPU) | No GPU required. |
| Front end | Vanilla JS, Chart.js (vendored) | No build step; no CDN (NFR-01). |
| Tests | pytest, httpx, hypothesis (optional) | Standard; property tests for metric monotonicity. |
| Lint and types | ruff, mypy | NFR-07. |

## 8. Deployment View

- One machine, one process, started by a single command. Binds to `127.0.0.1:8000`.
- Data in `data/`; key in a file outside `data/` with user-only permissions.
- Backups: copy `data/` and the key file while the app is stopped. Recommended: full-disk encryption (Windows device encryption).

## 9. Cross-Cutting Concerns

- **Privacy:** frames decoded in memory only; a logging filter removes payloads; responses never contain embeddings.
- **Security:** session cookie (HttpOnly, SameSite=Strict), CSRF on state changes, role checks, security headers, input size limits.
- **Observability:** access logs with method, path, status, latency and request id. No bodies.
- **Errors:** problem-details responses without payload echoes.
- **Configuration:** typed settings from environment and database; every change audited.

## 10. Quality Attributes

| Attribute | Approach |
|---|---|
| Correctness of metrics | Pure functions; hand-computed tests; cross-check against exported CSV. |
| Privacy | Minimal storage; encryption; redaction; export allowlist. |
| Reproducibility | Model and config recorded per trial; deterministic metrics. |
| Replaceability | Engine and matcher behind protocols. |
| Performance | Single-frame verify target under 1 second p95 on CPU; decimated curves. |

## 11. Architectural Decisions

| ID | Decision | Alternatives considered | Rationale |
|---|---|---|---|
| AD-1 | Modular monolith, local | Microservices; cloud service | Study tool; one operator; minimal attack surface. |
| AD-2 | Store embeddings, not images | Store frames | Privacy: frames are not needed for matching. |
| AD-3 | Max fusion over templates | Mean fusion | Standard in verification with multiple enrolment frames; mean kept as a later option. |
| AD-4 | Liveness separate from identity | Combined score | Avoids overclaiming security; keeps identity metrics clean. |
| AD-5 | Server-derived ground truth | Trust client label | Prevents mislabelled trials from skewing FAR and FRR. |
| AD-6 | SQLite with hash-chained audit | Postgres with triggers | Simplicity; tamper evidence without a server. |
| AD-7 | Fallback engine behind same protocol | Hard dependency on one library | Windows install risk (R1 in IMPLEMENTATION_PLAN.md). |
