# Feature List

**Traces to:** PRD.md, USE_CASES.md. **Used by:** IMPLEMENTATION_PLAN.md for scheduling.

Priority: **M** = Must, **S** = Should, **C** = Could (MoSCoW). Status column is blank for the implementer.

## Epic 1: Consent and Participants

| Feature | Description | Requirements | Use cases | Priority |
|---|---|---|---|---|
| F-1.1 Participant registry | Create, list and view participants by pseudonymous subject code. | FR-02 | UC-01 | M |
| F-1.2 Consent capture | Show versioned consent text; store hash, purposes and timestamp. | FR-01, NFR-13 | UC-01 | M |
| F-1.3 Consent withdrawal | One-action withdrawal that triggers template deletion and blocks use. | FR-04 | UC-07 | M |
| F-1.4 Optional display name | Encrypted optional name field. Off by default. | FR-02 | UC-01 | S |

## Epic 2: Enrolment and Verification

| Feature | Description | Requirements | Use cases | Priority |
|---|---|---|---|---|
| F-2.1 Guided enrolment | Live overlay (face found, move closer, centre face); captures 3 to 10 frames. | FR-03, NFR-09 | UC-01 | M |
| F-2.2 Quality gate | One face, detection score, minimum size, yaw limit, with reason codes. | FR-03a | UC-01, UC-02 | M |
| F-2.3 Encrypted template store | Embeddings stored only as encrypted vectors. | FR-03, NFR-06 | UC-01 | M |
| F-2.4 Re-enrolment | Replaces templates; old ones soft-deleted and audited. | FR-20 | UC-01 | S |
| F-2.5 1:1 verification | Score against claimed participant's templates; decision at threshold. | FR-05 | UC-02 | M |
| F-2.6 Live preview endpoint | Face and guidance check at about 3 fps; never returns embeddings. | NFR-09 | UC-01, UC-02 | M |
| F-2.7 Engine self-test | Health check of model: dimension and self-similarity. | FR-21 | UC-08 | S |

## Epic 3: Runs and Trials

| Feature | Description | Requirements | Use cases | Priority |
|---|---|---|---|---|
| F-3.1 Run management | Create, list, close and (admin) delete named runs with a protocol note. | FR-07, FR-15 | UC-03, UC-07 | M |
| F-3.2 Trial capture | Choose probe, claimed participant and condition tags; capture and submit. | FR-08 | UC-03 | M |
| F-3.3 Derived ground truth | Server derives genuine or impostor from labels; hint mismatch warned. | FR-08a | UC-03 | M |
| F-3.4 FTA recording | Records failures to acquire with reason; excluded from error rates. | FR-09 | UC-03 | M |
| F-3.5 Condition vocabulary | Controlled tag list set by admin (lighting, distance, glasses, pose, expression, background, camera). | FR-08, FR-06 | UC-03, UC-08 | M |
| F-3.6 Batch trials | Several frames for one probe and claimed pair, each recorded as a trial. | FR-08 | UC-03 | S |
| F-3.7 Trial browser | Filter by ground truth, outcome, tag; cursor pagination; trial detail without images. | FR-08 | UC-03, UC-04 | S |

## Epic 4: Metrics and Analysis

| Feature | Description | Requirements | Use cases | Priority |
|---|---|---|---|---|
| F-4.1 Error-rate metrics | FAR, FRR, GAR, accuracy, balanced accuracy, FTA rate, counts. | FR-10 | UC-04 | M |
| F-4.2 Confidence intervals | Wilson 95% intervals for each rate; subject-level bootstrap reported alongside. | FR-10 | UC-04 | M |
| F-4.3 Small-sample warnings | Warnings for class sizes under 30 and rule-of-three bounds above 1%. | FR-10 | UC-04 | M |
| F-4.4 Per-condition breakdown | Metrics per condition tag and an untagged row. | FR-10 | UC-04 | M |
| F-4.5 Threshold sweep | FAR(t) and FRR(t) over all candidate thresholds; decimated for display. | FR-11 | UC-05 | M |
| F-4.6 EER | Discrete and interpolated EER with threshold; interpolation labelled as approximate. | FR-11 | UC-05 | M |
| F-4.7 Curve plots | FAR and FRR vs threshold with operating point and EER marked. DET optional. | FR-12 | UC-05 | M (curve), C (DET) |
| F-4.8 Model and config display | Model name, version, dimension, detector, library versions shown on analysis page. | FR-19 | UC-04 | M |
| F-4.9 Liveness-gated comparison | Identity outcomes with and without liveness gating, as separate series. | FR-14 | UC-09 | C |

## Epic 5: Export and Reproducibility

| Feature | Description | Requirements | Use cases | Priority |
|---|---|---|---|---|
| F-5.1 Trial export | CSV of trials with metadata block and column allowlist. | FR-13 | UC-06 | M |
| F-5.2 Metrics export | Per-condition metrics CSV. | FR-13 | UC-06 | M |
| F-5.3 Sweep export | Full-resolution sweep CSV. | FR-13 | UC-06 | M |
| F-5.4 Reproducibility fields | Each trial stores model, threshold, app version, config hash. | NFR-03 | UC-03 | M |
| F-5.5 Standalone analysis script | Script that recomputes metrics and EER from an exported CSV, for independent checking. | PRD success criteria | UC-06 | S |

## Epic 6: Liveness (Optional)

| Feature | Description | Requirements | Use cases | Priority |
|---|---|---|---|---|
| F-6.1 Liveness check endpoint | Runs a configured liveness method; returns method, score, pass or fail. | FR-14 | UC-09 | C |
| F-6.2 Separate storage | Liveness fields kept apart from identity score fields. | FR-14, NFR-05 | UC-09 | C |
| F-6.3 Not-run handling | Trial recorded with liveness "not run" when disabled or unavailable. | FR-14 | UC-09 | C |

## Epic 7: Retention, Deletion and Privacy

| Feature | Description | Requirements | Use cases | Priority |
|---|---|---|---|---|
| F-7.1 Participant deletion | Anonymise (trials kept under alias) or purge (trials removed). | FR-15 | UC-07 | M |
| F-7.2 Template deletion | Deletes a participant's templates on demand. | FR-15 | UC-07 | M |
| F-7.3 Retention sweep | Dry run and live modes for expired frames and templates. | FR-16 | UC-07 | M |
| F-7.4 Debug frames (off by default) | Encrypted, expiring trial frames; maximum 24 hours. | FR-22 | UC-08 | C |
| F-7.5 Log redaction | Filter removes image payloads and banned keys from logs and errors. | NFR-05 | all | M |
| F-7.6 Frames never persisted | Frames decoded in memory and discarded before the response is built. | NFR-05, NFR-06 | UC-02 | M |

## Epic 8: Audit and Integrity

| Feature | Description | Requirements | Use cases | Priority |
|---|---|---|---|---|
| F-8.1 Audit events | Append-only record of all listed actions, with no biometric content. | FR-17 | all | M |
| F-8.2 Hash chain | Each event hashes the previous one; verification command and admin button. | FR-17 | UC-10 | M |
| F-8.3 Atomic trial write | Trial and its audit event in one transaction. | NFR-11 | UC-03 | M |
| F-8.4 Audit viewer | Admin view with filters and chain verification result. | FR-17 | UC-10 | S |

## Epic 9: Accounts, Settings and Administration

| Feature | Description | Requirements | Use cases | Priority |
|---|---|---|---|---|
| F-9.1 Login and roles | Local accounts with operator and admin roles; session cookie. | FR-18 | all | M |
| F-9.2 CSRF and rate limiting | Token on state changes; login rate limit. | FR-18 | UC-08 | M |
| F-9.3 Threshold setting | Admin sets operating threshold with a mandatory reason. | FR-06 | UC-08 | M |
| F-9.4 Settings management | View and change settings with reason and audit. | FR-06, FR-17 | UC-08 | M |
| F-9.5 Operator management | Create and disable operator accounts. | FR-18 | UC-08 | S |
| F-9.6 Bootstrap admin | Command to create the first admin account. | FR-18 | UC-08 | M |
| F-9.7 Security headers | Content-Security-Policy, nosniff, no-referrer, camera-only permissions policy. | NFR-01 | all | M |

## Epic 10: Platform and Quality

| Feature | Description | Requirements | Use cases | Priority |
|---|---|---|---|---|
| F-10.1 Versioned migrations | Schema created and changed by migration; startup checks head. | NFR-11 | all | M |
| F-10.2 Local-only binding | Binds to 127.0.0.1; warning if configured otherwise. | NFR-01 | all | M |
| F-10.3 Key file check | Refuses to start if the key file is readable by other users. | NFR-06 | all | M |
| F-10.4 Latency measurement | Records verify duration without payloads. | NFR-02 | UC-02 | S |
| F-10.5 Offline test suite | Tests run with a fake face engine; no webcam or model. | NFR-08 | all | M |
| F-10.6 Accessibility pass | Labels, focus order, contrast. | NFR-12 | all | S |

## Feature Count

| Priority | Count |
|---|---|
| Must | 42 |
| Should | 11 |
| Could | 5 |
| Total | 58 |
