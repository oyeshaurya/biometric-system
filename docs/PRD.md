# Product Requirements Document: Face-Recognition Performance Lab

**Version:** 1.0 (specification, pre-implementation)
**Status:** Draft for implementation handoff
**Related:** USE_CASES.md, FEATURES.md, ARCHITECTURE.md, SYSTEM_DESIGN.md, IMPLEMENTATION_PLAN.md

---

## 1. Problem

A student or researcher studying biometric authentication needs to measure how a face-verification system performs, not just whether it works once. Classroom demos (such as the BioID Playground) show a single accept or reject. They do not provide enough structured trials, controlled condition tags, correct error-rate definitions, threshold analysis, or privacy controls to support an honest evaluation.

## 2. Goals

| ID | Goal |
|---|---|
| G-1 | Run consented 1:1 face-verification trials from a webcam and log each one with ground truth and condition tags. |
| G-2 | Compute FAR, FRR, GAR, decision accuracy and balanced accuracy by test class and condition, with confidence intervals. |
| G-3 | Sweep the decision threshold, plot FAR and FRR against it, and report EER. |
| G-4 | Export results in a form that can be analysed and reproduced, without exporting biometric data. |
| G-5 | Handle consent, withdrawal, retention and deletion as product features, not afterthoughts. |
| G-6 | Keep identity verification and liveness (presentation-attack detection) as separate, clearly labelled functions. |

## 3. Non-Goals

- 1:N identification (searching a gallery for an unknown face).
- Multi-biometric fusion (face plus voice or fingerprint).
- Production deployment, multi-tenant hosting, or public internet access.
- Any claim of security against presentation attacks beyond what the optional liveness module measures on study data.
- Mobile apps.

## 4. Users and Roles

| Role | Description | Permissions |
|---|---|---|
| Operator | Runs the study sessions and enrols participants. | Consent, enrolment, verification, trials, metrics, export. |
| Admin | Owns the study configuration and data governance. | All operator permissions, plus threshold, deletion, retention, settings, operator accounts, audit viewer. |
| Analyst | Reads results. Often the same person as the operator. | Metrics, sweep, export (read-only). Treated as operator for permissions in v1. |
| Participant | Volunteer who gives consent and is enrolled and tested. Does not log in. | None. Consent is recorded by the operator. |

## 5. Scenarios

1. An operator enrols a consenting volunteer, captures five quality-checked frames, and sees which frames were rejected and why.
2. An operator runs 20 genuine and 20 impostor trials under a list of condition tags (lighting, distance, glasses). The app derives the ground truth and records every outcome.
3. An analyst opens the analysis page, sees FAR and FRR at the operating threshold, a per-condition table, and the threshold sweep with the EER marked.
4. A participant withdraws consent. The operator withdraws it in the app. The templates are deleted and the participant can no longer be verified.
5. An admin exports the trials as CSV with a metadata block and confirms that no images or embeddings are in the file.

## 6. Functional Requirements

Each requirement has a unique ID used across all documents.

| ID | Requirement | Priority |
|---|---|---|
| FR-01 | **Consent gate.** Store a consent record before any biometric capture: consent text version, SHA-256 of the consent text, purposes, accepted flag, timestamp, recording operator. Enrolment is refused without active consent. | Must |
| FR-02 | **Create participant.** Create a participant with a pseudonymous subject code (for example `P001`). Names are not stored by default. An optional display name is stored encrypted. | Must |
| FR-03 | **Enrolment.** Capture N frames (default 5, allowed 3 to 10). Each frame must pass the quality gate. Store one encrypted embedding per accepted frame. | Must |
| FR-03a | **Quality gate.** Exactly one face; detection score >= 0.6; face box >= 80 px on the shorter side; absolute yaw <= 30 degrees. Each rejection returns a reason code. | Must |
| FR-04 | **Withdraw consent.** Mark consent withdrawn, delete all templates (see FR-15), and block further enrolment and verification for that participant. | Must |
| FR-05 | **Verify 1:1.** Given a claimed participant and a probe frame, compute the score against that participant's active templates and return the decision at the operating or supplied threshold. | Must |
| FR-06 | **Operating threshold.** Admin reads and sets the threshold in [-1, 1] with a mandatory reason. Every change is audited. | Must |
| FR-07 | **Runs.** Create a named trial run with a protocol note. Each trial belongs to exactly one run. | Must |
| FR-08 | **Trial logging.** Store probe label, claimed label, ground truth, score, threshold used, outcome (accept, reject, fta), condition tags, model name and version, timestamps, duration, and liveness fields if run. | Must |
| FR-08a | **Ground-truth derivation.** Ground truth is derived on the server: genuine when probe label equals claimed label, impostor otherwise. A client hint that disagrees is overridden and the mismatch is returned as a warning. | Must |
| FR-09 | **Failure to acquire (FTA).** If no face is found or the quality gate fails, record the trial with outcome fta and a reason code. FTA trials are excluded from FAR and FRR and reported as a separate rate. | Must |
| FR-10 | **Metrics.** For a run, at a threshold, optionally filtered by tag, report FAR, FRR, GAR, decision accuracy, balanced accuracy, class counts, FTA rate, and 95% Wilson intervals. Include a per-tag breakdown. | Must |
| FR-11 | **Threshold sweep.** Compute FAR(t) and FRR(t) over all candidate thresholds for a run (optionally per tag). Return discrete and interpolated EER, the threshold at EER, and the operating threshold. | Must |
| FR-12 | **Curves.** Plot FAR and FRR against threshold with the operating threshold and EER marked. DET curve is optional. | Should |
| FR-13 | **CSV export.** Export trials, per-condition metrics, and the sweep table. Each file starts with a metadata block (run id, threshold, model name and version, app version, timestamp). Embeddings, images and landmarks are never exported. | Must |
| FR-14 | **Liveness (optional, separate).** Run a liveness check on a frame. Return score, method and pass or fail. Store it in separate fields. It never enters the identity score. | Could |
| FR-15 | **Deletion.** Admin can delete a participant's templates, delete a participant (mode anonymise keeps trial rows under an alias; mode purge removes their trials), and delete a run. | Must |
| FR-16 | **Retention sweep.** Delete expired debug frames and templates past the retention period. Support a dry run. | Must |
| FR-17 | **Audit log.** Append-only, hash-chained record of consent events, participant changes, enrolment, verification (summary), trial creation, threshold change, export, deletion, retention, login and logout, and settings changes. | Must |
| FR-18 | **Authentication and roles.** Local accounts with operator and admin roles. Login required for all API routes except health. | Must |
| FR-19 | **Model transparency.** Show model name, version, embedding dimension, detector, and library versions in the UI and in every export. | Must |
| FR-20 | **Re-enrolment.** Running enrolment again replaces the template set. Previous templates are soft-deleted and audited. | Should |
| FR-21 | **Engine self-test.** A health endpoint runs the face engine on a bundled image and checks embedding dimension and self-similarity. | Should |
| FR-22 | **Debug frames (off by default).** If an admin enables it, trial frames are stored encrypted with a mandatory expiry of at most 24 hours. | Could |

## 7. Non-Functional Requirements

| ID | Requirement | Measure |
|---|---|---|
| NFR-01 | **Local-first.** Bind to 127.0.0.1 by default. No runtime outbound network calls. Front-end libraries are vendored, not loaded from a CDN. | Network capture during a session shows no external requests. |
| NFR-02 | **Latency.** Verify p95 under 1 second on the test laptop CPU for one 640 px frame, excluding webcam time. | Measured and recorded in docs/benchmarks.md. |
| NFR-03 | **Reproducibility.** Each trial records model, threshold, app version and a hash of the active configuration. Metric functions are deterministic. | Same inputs give identical outputs. |
| NFR-04 | **Metric correctness.** Rate and EER functions are tested against hand-computed examples to 1e-9. | Unit tests pass. |
| NFR-05 | **Privacy in logs.** No images, base64 payloads, embeddings or landmarks in logs, errors or exports. | Redaction tests pass. |
| NFR-06 | **Encryption at rest for templates.** Authenticated symmetric encryption; key stored outside the database and data folder. | Key file permission check; tamper test. |
| NFR-07 | **Maintainability.** Layered design. Face engine and matcher behind interfaces. Static checks clean. | Lint and type-check pass on core. |
| NFR-08 | **Testability.** At least 85% line coverage on metrics and services. CI tests run without a webcam or model download. | Coverage report. |
| NFR-09 | **Usability.** Live guidance overlay on the capture page. Starting a trial takes at most two clicks after choosing the participant. | Manual checklist. |
| NFR-10 | **Portability.** Windows 11 with Python 3.11 is primary. | Install and run on the target laptop. |
| NFR-11 | **Integrity.** A trial and its audit event are written in one transaction. Schema changes use versioned migrations. | Transaction test; migration test. |
| NFR-12 | **Accessibility.** Keyboard-operable forms, labelled controls, WCAG AA contrast. | Manual accessibility pass. |
| NFR-13 | **Ethics support.** Consent text and study notice shown on the enrolment page. Withdrawal is one action. | UI check. |
| NFR-14 | **Concurrency.** SQLite in WAL mode. Single operator at a time is the design target. | Documented limit. |

## 8. Success Criteria

- All Must requirements pass their acceptance tests (see SYSTEM_DESIGN.md section 9).
- A complete pilot run (3 to 5 volunteers) produces an exported CSV that a separate script reproduces: same FAR, FRR and EER to 1e-9.
- The manual webcam checklist (IMPLEMENTATION_PLAN.md) is fully ticked before data collection starts.
- No biometric content is found in the database export, logs, or CSV files during a checklist audit.

## 9. Assumptions

- Single machine, single operator at a time, bound to localhost.
- Windows 11, Python 3.11, CPU inference is acceptable.
- Webcam at 720p or better, reasonable indoor lighting.
- Participants are adults who consent under an approved ethics protocol.
- Matching uses cosine similarity on L2-normalised embeddings. No score normalisation in v1.
- One probe frame per verification trial.
- The study measures performance. It is not a deployment.

## 10. Constraints and Dependencies

- Face models: InsightFace pretrained weights are for non-commercial research use. Fallback: OpenCV Zoo YuNet (detector) and SFace (recogniser). Licence recorded in docs/model_licences.md.
- Ethics approval must be in place before participant data is collected.
- If the study is subject to GDPR or a similar regime, a data protection note is required.

## 11. Open Decisions (need the owner's answer before data collection)

| # | Decision | Why it matters |
|---|---|---|
| D-1 | Is ethics approval in place, and what retention and anonymisation does it require? | Sets retention defaults and what may be stored. |
| D-2 | Which data protection regime applies? | Sets lawful basis wording, retention and rights handling. |
| D-3 | Target participant count and impostor-pool size. | Sets sample sizes and the protocol. |
| D-4 | Must liveness be measured quantitatively? | If yes, a presentation-attack dataset is needed and FR-14 grows. |
| D-5 | Is the fallback engine acceptable if InsightFace will not install on Windows? | Changes the model adapter and the reported model name. |

## 12. Glossary

- **Genuine attempt:** probe is the enrolled person they claim to be.
- **Impostor attempt:** probe is a different person from the one claimed.
- **FAR (false acceptance rate):** share of impostor attempts accepted.
- **FRR (false rejection rate):** share of genuine attempts rejected.
- **GAR (genuine acceptance rate):** 1 minus FRR.
- **EER (equal error rate):** the operating point where FAR equals FRR.
- **FTA (failure to acquire):** no usable face was captured, so no decision was made.
- **Liveness:** a check that the capture is from a live person rather than a photo, replay or synthetic input. Separate from identity matching.
