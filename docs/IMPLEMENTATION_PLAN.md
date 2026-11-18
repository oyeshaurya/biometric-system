# Implementation Plan

**Traces to:** PRD.md, USE_CASES.md, FEATURES.md, ARCHITECTURE.md, SYSTEM_DESIGN.md.
**Audience:** the implementer (Opus, or a developer) building the system from this pack.

Effort figures are rough and assume part-time work. Milestones are ordered. Do not start participant data collection before the M13 gate.

---

## 0. How to Use This Plan

1. Build milestones in order. Each has an exit criterion. Do not move on until it is met.
2. Every task names the requirement IDs it satisfies. Keep those IDs in commit messages and test names.
3. Write metric tests before the metric code (test-first for `core/metrics`).
4. A change to any requirement or interface is made in the spec first, then in code.

## 1. Milestone Summary

| ID | Milestone | Effort | Depends on | Exit criterion |
|---|---|---|---|---|
| M0 | Setup and feasibility spike | 0.5 week | none | Model self-test prints embedding and self-similarity above 0.99 |
| M1 | Metrics core | 1 week | M0 (not required, can start in parallel) | Metric tests green; core/metrics coverage at least 95% |
| M2 | Persistence, config, security, audit | 1 week | M0 | Migrations up and down; crypto, audit chain and settings tests green |
| M3 | Face engine adapter and matcher | 1 week | M0, M2 | Fake engine integration works; real self-test passes locally |
| M4 | Participants, consent, enrolment | 1 week | M2, M3 | UC-01 and UC-07 withdrawal integration tests pass |
| M5 | Verification | 0.5 week | M3, M4 | UC-02 integration tests pass; p95 latency recorded |
| M6 | Runs and trials | 1 week | M5 | UC-03 integration tests pass, including FTA and mismatch paths |
| M7 | Metrics, by-condition and sweep API | 0.5 week | M1, M6 | UC-04 and UC-05 integration tests pass |
| M8 | Browser UI | 1.5 weeks | M4 to M7 | Manual checklist items for capture, enrol, verify, trial pass |
| M9 | Export | 0.5 week | M6, M7 | Exports open in a spreadsheet and pass the allowlist test |
| M10 | Retention, deletion, audit UI | 0.5 week | M2, M6 | UC-07 and FR-16 tests pass |
| M11 | Authentication and hardening | 0.5 week | M2 | Auth and redaction tests green |
| M12 | Liveness (optional) | 1 week | M5, M6 | Route works; storage separate; documented |
| M13 | Evaluation protocol and write-up | 2 weeks, gated | all above, ethics approval | Dataset frozen; analysis reproducible from exports |

Total build (M0 to M11, excluding optional M12 and data collection): about 9 to 10 weeks part-time.

## 2. Milestone Detail

### M0. Setup and feasibility spike

Requirements: NFR-07, NFR-10, FR-21, D-5.

1. Create `pyproject.toml`. Runtime dependencies: fastapi, uvicorn, sqlalchemy, alembic, pydantic, pydantic-settings, cryptography, argon2-cffi, numpy, opencv-python-headless, onnxruntime, insightface. Dev dependencies: pytest, httpx, ruff, mypy, hypothesis.
2. Create a Python 3.11 virtual environment and install.
3. Create the folder layout from ARCHITECTURE.md section 6, plus `.gitignore` (data/, models/, .env, *.db, key files).
4. Spike: run InsightFace (`buffalo_l`) on two photos in a scratch script outside the project. Record install problems, model download path and licence text in `docs/model_licences.md`.
5. If InsightFace fails to install on Windows (typical causes: C++ build tools missing, onnxruntime mismatch), switch to the fallback: OpenCV Zoo YuNet and SFace, installed with pip and no compilation. Record the decision in the README and `docs/model_licences.md`.

**Exit:** `scripts/self_test.py` prints model info, a 512-dimensional (or SFace equivalent) embedding, and self-similarity above 0.99.

### M1. Metrics core (pure functions)

Requirements: FR-10, FR-11, NFR-04, NFR-03.

1. Implement `core/metrics/rates.py` (FAR, FRR, GAR, accuracy, balanced accuracy), `wilson.py`, `sweep.py`, `eer.py`. numpy only, no I/O.
2. Write the unit tests from SYSTEM_DESIGN.md section 9.1 first, including the hand-computed examples.
3. Implement the EER algorithm from SYSTEM_DESIGN.md section 8.4 exactly, including the edge cases.
4. Add `scripts/metrics_demo.py` that reads a CSV of scores (columns: label, score) and prints FAR, FRR and EER. This is an independent check used later.

**Exit:** metric tests green; coverage of `core/metrics` at least 95%.

### M2. Persistence, configuration, security and audit

Requirements: NFR-06, NFR-11, FR-06, FR-17, FR-18 (partial), F-10.1, F-10.3, F-8.2.

1. `config.py` with pydantic-settings: database URL, key file path, bind address, retention defaults, condition vocabulary, quality thresholds.
2. `db/models.py` for every table in SYSTEM_DESIGN.md section 1. `db/session.py` sets WAL mode and foreign keys on.
3. Alembic `0001_initial`. Startup check that the database is at head.
4. `core/security/crypto.py` (Fernet, MultiFernet, key file permission check) and `passwords.py` (argon2id).
5. `services/audit.py`: hash-chained append and `verify()`. Triggers block UPDATE and DELETE on `audit_events`.
6. `services/settings.py`: typed get and set; reason required; old and new values audited.
7. `scripts/create_admin.py` for the first admin.
8. `scripts/verify_audit_chain.py`.

**Exit:** crypto, audit chain and settings tests green; migration up and down clean.

### M3. Face engine adapter and matcher

Requirements: FR-03a, FR-05 (scoring), FR-19, FR-21, AD-3, AD-7.

1. `core/face/base.py`: `FaceDetection`, `ModelInfo`, `FaceEngine` protocol.
2. `core/face/fake_engine.py`: seeded identity and noise, as in SYSTEM_DESIGN.md section 9.2.
3. `core/face/insightface_engine.py` (or the YuNet and SFace variant chosen in M0). Lazy model loading. Checksum verification of weights before loading.
4. `core/face/quality.py`: the FR-03a rules, with thresholds read from settings.
5. `core/matching/cosine.py`: max fusion, zero-vector guard.
6. Model-tagged tests in `tests/model/`.

**Exit:** fake-engine integration works; real self-test passes locally; per-frame latency recorded.

### M4. Participants, consent and enrolment

Requirements: FR-01, FR-02, FR-03, FR-04, FR-20, NFR-13, F-1.1 to F-1.4, F-2.1, F-2.3, F-2.4.

1. `services/participants.py`, `services/enrolment.py`.
2. Routes for participants, consent, withdrawal, enrolment and template deletion.
3. Consent text file in `docs/` with version. The consent route checks the hash against the file.
4. Re-enrolment: soft-delete old templates, store new ones, audit both.
5. Integration tests for consent and enrolment (SYSTEM_DESIGN.md section 9.2).

**Exit:** UC-01 and the withdrawal part of UC-07 pass integration tests.

### M5. Verification

Requirements: FR-05, FR-09, NFR-02, F-2.5, F-2.6, F-10.4.

1. `services/verification.py` implementing the ordering in SYSTEM_DESIGN.md section 4: consent check first, decode in memory, analyse, quality gate, score, decide, discard.
2. `/api/verify` and `/api/verify/preview`. Preview is rate-limited.
3. Duration middleware that records time only, never payloads.

**Exit:** UC-02 integration tests pass; p95 latency measured with the fake engine and with the real engine.

### M6. Runs and trials

Requirements: FR-07, FR-08, FR-08a, FR-09, NFR-03, NFR-11, F-3.1 to F-3.5.

1. `services/trials.py`: ground-truth derivation; FTA recording; warning on hint mismatch; trial and audit event written in one transaction.
2. Run create, list, close and delete (delete requires typing the run name).
3. Trial list and detail with filters and cursor pagination. Detail never includes images.
4. `scripts/make_synthetic_run.py` for UI development without participants.

**Exit:** UC-03 integration tests pass, including FTA and mismatch paths.

### M7. Metrics, by-condition and sweep API

Requirements: FR-10, FR-11, F-4.1 to F-4.8.

1. `services/metrics.py`: loads a run's scores from the database and calls `core/metrics`.
2. Endpoints from SYSTEM_DESIGN.md section 3.5.
3. Cross-check test: endpoint values equal a direct computation over the DB rows.

**Exit:** UC-04 and UC-05 integration tests pass.

### M8. Browser UI

Requirements: NFR-01, NFR-09, NFR-12, FR-12, F-2.1, F-2.6, F-4.7.

1. `static/js/camera.js`: getUserMedia; canvas capture at 640 px wide; JPEG at quality 0.9; permission-denied path; stop tracks when the page is hidden.
2. `static/js/guidance.js`: calls the preview endpoint about 3 times a second; shows guidance text.
3. Pages: login; participants and consent (with consent text); enrol; verify; trial runner (condition-tag selector, derived ground truth shown); runs list; analysis (metrics table, per-tag table, FAR and FRR chart with EER and operating-threshold markers, optional DET); admin (settings with reason field, operators, retention, audit viewer with chain check).
4. Vendor Chart.js into `static/vendor/`. CSP allows self only.
5. Accessibility pass: labels, focus order, contrast.

**Exit:** manual checklist items for capture, enrol, verify and trials pass.

### M9. Export

Requirements: FR-13, F-5.1 to F-5.3, F-5.5.

1. `services/export.py`: column allowlist per export type; metadata block.
2. Routes from SYSTEM_DESIGN.md section 3.7; each writes an audit event.
3. Tests: contents, allowlist, row count, no base64.
4. `scripts/` standalone analysis script that recomputes metrics from an exported CSV.

**Exit:** exports open cleanly in a spreadsheet; the standalone script reproduces FAR, FRR and EER from the export.

### M10. Retention, deletion and audit UI

Requirements: FR-15, FR-16, FR-17, FR-22 (optional), F-7.1 to F-7.4, F-8.4.

1. `services/retention.py`: dry run and live sweeps; anonymise (keyed alias) and purge modes for participants; run deletion.
2. Debug frames: off by default; if enabled, encrypted and expiring within 24 hours.
3. Admin retention page and audit viewer with chain verification.

**Exit:** UC-07 and FR-16 tests pass; deletion checklist items pass.

### M11. Authentication and hardening

Requirements: FR-18, NFR-01, NFR-05, NFR-06, F-7.5, F-7.6, F-9.1 to F-9.7, F-10.2, F-10.3.

1. Login, logout, sessions, CSRF, roles, login rate limit.
2. Security headers, body and image size limits, format sniffing.
3. Redaction filter on logging; end-to-end redaction test.
4. Refuse to start with a bad key file permission; warn if bound to a non-loopback address.
5. Bootstrap admin command.

**Exit:** auth and redaction tests green; relevant checklist items pass.

### M12. Liveness (optional)

Requirements: FR-14, F-6.1 to F-6.3, F-4.9.

1. `core/liveness/base.py` and `none.py` (returns not run). Route returns 503 when disabled.
2. Choose one method, decided by the owner (D-4):
   - a passive ONNX anti-spoof model if its licence permits research use; or
   - a simple active challenge (blink or head turn, using landmarks), which needs no external model.
3. Store liveness fields on trials. Analysis shows identity outcomes with and without liveness gating as separate, labelled series.
4. Report only what is measured. APCER and BPCER need a presentation-attack dataset collected under ethics approval; without one, state the limitation.

**Exit:** route works; storage is separate; documented as optional.

### M13. Evaluation protocol and write-up (gated)

Requirements: PRD sections 8 and 11.

**Gate (must be complete first):**
- Ethics approval recorded in `docs/ethics_and_privacy.md` (D-1).
- Data protection regime confirmed and noted (D-2).
- Consent text approved.
- Sample sizes decided (D-3).

Steps:
1. Write `docs/protocol.md`: participant numbers, sessions, condition tags and levels, trials per condition, development and test split for threshold selection.
2. Pilot with 3 to 5 volunteers. Fix UI and protocol issues. Re-run the manual checklist.
3. Collect data.
4. Select the operating threshold on the development split only (EER on development, or a target FAR). Report all rates on the test split.
5. Produce figures: FAR and FRR curves, DET, per-condition bars. Tables with Wilson and subject-level bootstrap intervals.
6. Write `docs/methodology.md` and the limitations section.
7. Re-run the standalone analysis script on the frozen exports and confirm the numbers match.

**Exit:** dataset frozen; analysis reproducible from exports; write-up drafted.

## 3. Build Order Summary (critical path)

M0 then M2 then M3 then M4 then M5 then M6 then M7 then M8 then M9 then M10 then M11, with M1 in parallel from the start. M12 is optional. M13 starts only after the gate.

## 4. Manual Webcam Checklist

Run once per build before data collection. Record date, laptop and browser.

- [ ] Camera permission prompt appears; denying it shows an explanation and the camera light stays off.
- [ ] Granting permission shows a live preview; the camera light is on only while the capture page is open.
- [ ] Closing the tab turns the camera light off within a few seconds.
- [ ] Guidance overlay: "no face" when covered; "move closer" at about 2 m; "centre your face" when off-axis.
- [ ] Enrol one participant with 5 frames; accepted count shown; yaw rejection appears when the head is turned.
- [ ] Verify genuine 10 times at about 0.5 m, 1 m and 1.5 m; scores recorded and decisions match the threshold.
- [ ] Verify an impostor (second volunteer with consent) 10 times; decisions recorded.
- [ ] Bright, dim and backlit conditions are each tagged correctly.
- [ ] Glasses on and off are tagged correctly.
- [ ] A trial with a mismatched ground-truth hint shows a warning and stores the server-derived value.
- [ ] Metrics page values match a manual count from the trials table.
- [ ] Sweep plot shows the operating threshold and EER markers.
- [ ] CSV export opens in a spreadsheet, has the metadata block, and contains no base64 text.
- [ ] `data/logs/app.log` contains no base64 text after the session.
- [ ] `biometric.db` opened in a SQLite browser shows templates as unreadable ciphertext.
- [ ] Withdraw consent for the test participant: templates gone, verification returns 409, audit shows events.
- [ ] Audit chain verification passes.
- [ ] Retention dry run reports expected counts; live run deletes expired debug frames.
- [ ] Application refuses to start when the key file is readable by another user.

## 5. Risks

| # | Risk | Likelihood / Impact | Mitigation | Owner milestone |
|---|---|---|---|---|
| R1 | InsightFace fails to install or build on Windows | Medium / High | M0 spike; YuNet and SFace fallback behind the same protocol | M0 |
| R2 | Model licence does not permit the intended use | Low for academic use / High | Read and record licence in M0; fallback engine | M0 |
| R3 | Small samples give wide, uninformative intervals | High / Medium | Target participant counts; warnings; honest reporting | M13 |
| R4 | Trials within a participant are correlated, inflating confidence | High / Medium | Subject-level bootstrap reported with Wilson | M7, M13 |
| R5 | Threshold tuned on the data it is evaluated on | Medium / High | Development and test split; threshold reason recorded | M13 |
| R6 | Impostor trials need other people's biometric data | Medium / High | Consented impostor pool under ethics approval; synthetic-only runs for development | M13 |
| R7 | Ethics or data protection non-compliance | Medium / High | M13 gate; consent versioning; retention schedule | M4, M13 |
| R8 | Lighting or camera variation dominates results | High / Medium | Condition tags; per-tag analysis; report variation | M7, M13 |
| R9 | Local attacker reads templates with the key file | Low / Medium | Key outside data folder; ACL; device encryption; documented limit | M2, M11 |
| R10 | Key loss makes templates unreadable | Low / Low | Re-enrolment is the recovery path; key backup procedure in README | M2 |
| R11 | Scope creep into 1:N or liveness claims | High / Medium | Out-of-scope list in PRD; liveness reported only as measured | M12 |
| R12 | CPU latency too high for a comfortable UI | Medium / Low | Lower preview rate; smaller detector input; latency reported | M5, M8 |
| R13 | SQLite contention or corruption on abrupt shutdown | Low / Medium | WAL mode; single operator; backup by copy when stopped | M2 |
| R14 | Browser camera API differences | Medium / Low | Test one Chromium-based browser; use localhost (secure context) | M8 |
| R15 | Audit log tampering undetected | Low / Medium | Hash chain plus verify command; print the chain head into the study record periodically | M2, M10 |

## 6. Decisions Needed Before Build or Data Collection

| # | Decision | Needed by |
|---|---|---|
| D-1 | Ethics approval status and its retention and anonymisation requirements | Before M4 (consent text) and always before M13 |
| D-2 | Applicable data-protection regime | Before M10 (retention defaults) |
| D-3 | Target participant count and impostor-pool size | Before M13 |
| D-4 | Whether liveness is evaluated quantitatively | Before M12 |
| D-5 | Whether the fallback engine is acceptable if InsightFace will not install | Decided at M0 |

## 7. Definition of Done (for every milestone)

- Requirement IDs in the milestone are satisfied and cited in tests or commit messages.
- New code has tests; `core/metrics` tests are written first.
- `ruff` and `mypy` pass on changed files.
- No biometric content in logs or exports (redaction tests pass).
- Docs updated if an interface, endpoint or requirement changed.
