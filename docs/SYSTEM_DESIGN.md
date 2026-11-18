# System Design

**Traces to:** PRD.md, USE_CASES.md, ARCHITECTURE.md. **Used by:** IMPLEMENTATION_PLAN.md.

Contents: 1 Data model · 2 Migrations · 3 REST API · 4 Verification sequence · 5 Security and privacy · 6 Retention defaults · 7 Liveness boundary · 8 Metrics and EER · 9 Test strategy · 10 Error model.

---

## 1. Data Model (SQLite, SQLAlchemy 2.x)

Timestamps are UTC ISO-8601. Enumerations are constrained VARCHAR columns.

### 1.1 participants
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| subject_code | VARCHAR(32) UNIQUE NOT NULL | pseudonymous, for example `P001` |
| display_name_enc | BLOB NULL | Fernet ciphertext, optional |
| status | VARCHAR(16) | active, withdrawn, anonymised, deleted |
| alias | VARCHAR(24) UNIQUE | keyed HMAC alias, used after anonymisation |
| created_at, updated_at | DATETIME | |

### 1.2 consents
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| participant_id | FK participants NOT NULL | |
| consent_version | VARCHAR(32) NOT NULL | |
| consent_text_sha256 | CHAR(64) NOT NULL | hash of the text shown |
| purposes | JSON NOT NULL | for example `["research_face_verification_eval"]` |
| accepted | BOOLEAN NOT NULL | |
| granted_at | DATETIME NOT NULL | |
| withdrawn_at | DATETIME NULL | never deleted, only marked |
| recorded_by | FK operators | |

Index: (participant_id, withdrawn_at).

### 1.3 templates
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| participant_id | FK participants NOT NULL | |
| enrolment_batch_id | VARCHAR(36) NOT NULL | UUID |
| model_name, model_version | VARCHAR | |
| dim | SMALLINT NOT NULL | for example 512 |
| vector_enc | BLOB NOT NULL | Fernet ciphertext of float32 bytes |
| quality_json | JSON NOT NULL | detection score, box size, yaw; no features |
| created_at | DATETIME NOT NULL | |
| deleted_at | DATETIME NULL | soft delete, hard delete by retention |

Index: (participant_id, deleted_at).

### 1.4 runs
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| name | VARCHAR(120) UNIQUE NOT NULL | |
| description | TEXT | protocol note |
| threshold_snapshot | FLOAT NOT NULL | operating threshold at creation |
| model_name, model_version | VARCHAR | snapshot |
| config_hash | CHAR(64) | hash of relevant configuration |
| status | VARCHAR(16) | open, closed, deleted |
| created_at, closed_at | DATETIME | |

### 1.5 trials
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| run_id | FK runs NOT NULL | |
| probe_label | VARCHAR(64) NOT NULL | subject code or alias |
| claimed_label | VARCHAR(64) NOT NULL | |
| probe_participant_id | FK participants NULL | null if unenrolled or after anonymisation |
| claimed_participant_id | FK participants NULL | |
| ground_truth | VARCHAR(10) NOT NULL | genuine, impostor (server-derived) |
| outcome | VARCHAR(8) NOT NULL | accept, reject, fta |
| score | FLOAT NULL | null for fta |
| threshold | FLOAT NOT NULL | threshold used |
| fta_reason | VARCHAR(32) NULL | NO_FACE, MULTIPLE_FACES, FACE_TOO_SMALL, LOW_DET_SCORE, EXCESSIVE_YAW, NO_TEMPLATES |
| template_count | SMALLINT | |
| condition_tags | JSON NOT NULL | from the controlled vocabulary |
| model_name, model_version | VARCHAR | |
| liveness_method | VARCHAR(32) NULL | |
| liveness_score | FLOAT NULL | |
| liveness_passed | BOOLEAN NULL | |
| duration_ms | INTEGER | |
| created_at | DATETIME NOT NULL | |

Indexes: (run_id, ground_truth, outcome); (claimed_participant_id); (probe_participant_id).

Labels are kept on the trial so impostor analysis still works after a participant is anonymised.

### 1.6 debug_frames (only when FR-22 is enabled)
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| trial_id | FK trials | |
| path | VARCHAR(260) | encrypted file in data/debug/ |
| expires_at | DATETIME NOT NULL | at most 24 hours after creation |

### 1.7 settings
| Column | Type | Notes |
|---|---|---|
| key | VARCHAR(64) PK | for example operating_threshold, quality.min_det_score |
| value_json | JSON NOT NULL | |
| reason | TEXT NOT NULL | required on change |
| updated_at | DATETIME | |
| updated_by | FK operators | |

### 1.8 operators
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| username | VARCHAR(64) UNIQUE | |
| password_hash | VARCHAR(255) | argon2id |
| role | VARCHAR(16) | operator, admin |
| disabled | BOOLEAN | |
| created_at | DATETIME | |

### 1.9 audit_events (append-only)
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| ts | DATETIME NOT NULL | |
| actor_id | FK operators NULL | null for system |
| action | VARCHAR(48) NOT NULL | for example consent.granted, trial.created |
| entity_type | VARCHAR(32) | |
| entity_id | VARCHAR(64) | |
| summary_json | JSON | numbers and codes only, no biometric content |
| request_id | VARCHAR(36) | |
| prev_hash | CHAR(64) | hash of the previous event |
| row_hash | CHAR(64) NOT NULL | SHA-256 of canonical JSON of this row plus prev_hash |

UPDATE and DELETE are blocked by triggers. `scripts/verify_audit_chain.py` recomputes the chain.

### 1.10 Relationships

- participant 1..n consents, templates; participant 0..n trials (as probe or claimed)
- run 1..n trials; trial 0..n debug_frames
- operator 0..n audit_events (actor)

## 2. Migrations

- Alembic from the first commit. `0001_initial` creates all tables above.
- Startup checks that the database is at head; the app refuses to run otherwise.
- Test: upgrade to head on an empty database, downgrade to base, upgrade again.

## 3. REST API

Base path `/api`. JSON unless stated. Errors use RFC 7807 problem details:

```json
{"type": "...", "title": "...", "status": 422, "detail": "...", "code": "NO_FACE"}
```

Images: JPEG or PNG, base64 in `image_b64`, at most 2 MB, at most 1920 x 1080 after decode.

Auth: `POST /api/auth/login` sets an HttpOnly, SameSite=Strict session cookie. State-changing requests require an `X-CSRF-Token` header. Roles: **O** operator, **A** admin.

### 3.1 Auth and health

| Method | Path | Role | Request | Response |
|---|---|---|---|---|
| POST | /api/auth/login | none | `{"username","password"}` | 200 `{"user":{"id","username","role"},"csrf_token"}` |
| POST | /api/auth/logout | O | none | 204 |
| GET | /api/health | none | none | 200 `{"status":"ok","db":"head","app_version"}` |
| GET | /api/health/engine | O | none | 200 `{"model":{...},"self_test":{"dim","self_similarity","passed"}}` |

### 3.2 Participants and consent

| Method | Path | Role | Request | Response |
|---|---|---|---|---|
| POST | /api/participants | O | `{"subject_code":"P001","display_name":null}` | 201 `{"id","subject_code","status","alias"}` |
| GET | /api/participants?status=&q= | O | none | 200 `{"items":[...],"total"}` |
| GET | /api/participants/{id} | O | none | 200 `{id,subject_code,status,consent,template_count}` |
| POST | /api/participants/{id}/consent | O | `{"consent_version","consent_text_sha256","purposes","accepted"}` | 201 `{"id","granted_at"}`; 422 if accepted is false |
| POST | /api/participants/{id}/consent/withdraw | O | `{"reason"}` | 200 `{"withdrawn_at","templates_deleted"}` |
| DELETE | /api/participants/{id}?mode=anonymise\|purge | A | `{"confirm":"P001"}` | 200 `{"mode","trials_affected"}` |

### 3.3 Enrolment and verification

| Method | Path | Role | Request | Response |
|---|---|---|---|---|
| POST | /api/participants/{id}/enrolment | O | `{"frames":[{"image_b64"}...],"replace":true}` | 200 `{"batch_id","accepted","rejected":[{"index","reason"}],"templates":[{"id","quality"}]}` |
| POST | /api/participants/{id}/templates/delete | A | `{"reason"}` | 200 `{"deleted"}` |
| POST | /api/verify | O | `{"claimed_participant_id","image_b64","threshold":null,"liveness":false}` | 200 `{"score","threshold","decision","template_count","quality","liveness"}` |
| POST | /api/verify/preview | O | `{"image_b64"}` | 200 `{"faces","det_score","bbox","yaw_deg","guidance":[...]}`; no embedding; rate-limited to 5 per second |

`decision` is `accept` or `reject`. Errors: 422 quality or FTA (with `code`), 409 consent inactive, 404 unknown participant.

### 3.4 Runs and trials

| Method | Path | Role | Request | Response |
|---|---|---|---|---|
| POST | /api/runs | O | `{"name","description"}` | 201 `{"id","threshold_snapshot","model"}` |
| GET | /api/runs | O | none | 200 `{"items":[{id,name,status,trial_count}]}` |
| POST | /api/runs/{id}/close | O | none | 200 `{"closed_at"}` |
| DELETE | /api/runs/{id} | A | `{"confirm":"<run name>"}` | 200 `{"trials_deleted"}` |
| POST | /api/runs/{id}/trials | O | `{"probe_label","claimed_label","ground_truth_hint","condition_tags","image_b64"}` | 201 `{"id","ground_truth","outcome","score","threshold","fta_reason","warnings"}` |
| GET | /api/runs/{id}/trials?ground_truth=&outcome=&tag=&limit=&cursor= | O | none | 200 `{"items","next_cursor"}` |
| GET | /api/trials/{id} | O | none | 200 full trial record, no images |

`ground_truth_hint` is optional. If it disagrees with the labels, the response carries a warning and the server value is stored.

### 3.5 Metrics and sweep

| Method | Path | Role | Parameters | Response |
|---|---|---|---|---|
| GET | /api/runs/{id}/metrics | O | `threshold` (default: snapshot), `tag` | 200 `{threshold,n_genuine,n_impostor,n_fta,fta_rate,far,far_ci95,frr,frr_ci95,gar,gar_ci95,accuracy,balanced_accuracy,warnings}` |
| GET | /api/runs/{id}/metrics/by-condition | O | `threshold` | 200 `{"rows":[{tag,n_genuine,n_impostor,far,frr,gar,accuracy}],"untagged"}` |
| GET | /api/runs/{id}/sweep | O | `tag`, `max_points` (default 1000) | 200 `{"curve":{thresholds,far,frr},"eer":{"discrete","interpolated"},"operating_threshold","n_genuine","n_impostor"}` |

### 3.6 Liveness (optional)

| Method | Path | Role | Request | Response |
|---|---|---|---|---|
| POST | /api/liveness/check | O | `{"image_b64","trial_id"}` | 200 `{"method","score","passed","reason"}`; 503 if unavailable. Never returns identity data. |

### 3.7 Export

| Method | Path | Role | Response |
|---|---|---|---|
| GET | /api/runs/{id}/export/trials.csv | O | text/csv with metadata block |
| GET | /api/runs/{id}/export/metrics.csv?tag= | O | per-condition metrics |
| GET | /api/runs/{id}/export/sweep.csv?tag= | O | full-resolution sweep |

Each export writes an audit event (type, run id, row count).

### 3.8 Settings, admin and audit

| Method | Path | Role | Request | Response |
|---|---|---|---|---|
| GET | /api/settings | A | none | 200 `{key: value}` |
| PUT | /api/settings/{key} | A | `{"value","reason"}` | 200 `{"key","old","new","audit_id"}` |
| POST | /api/admin/retention/run | A | `{"dry_run":true}` | 200 `{"debug_frames_deleted","templates_deleted"}` |
| GET | /api/admin/operators | A | none | list |
| POST | /api/admin/operators | A | `{"username","password","role"}` | 201 |
| GET | /api/audit?action=&limit=&cursor= | A | none | 200 `{"items"}` |
| GET | /api/audit/verify | A | none | 200 `{"valid","events"}` |

## 4. Verification Sequence

```
Browser          API route          VerificationService     FaceEngine    Template store    Matcher     DB + audit
  | POST /verify  |                        |                    |               |              |           |
  |-------------->| auth, CSRF, size check |                    |               |              |           |
  |               |-- verify(claimed,img)->|                    |               |              |           |
  |               |                        | check consent (before any decode)  |              |           |
  |               |                        |------------------------------------------------------------->|
  |               |                        | decode image in memory                                      |
  |               |                        | analyse(img) ----->|               |              |           |
  |               |                        |<-- faces, emb -----|               |              |           |
  |               |                        | if faces != 1 or quality fails -> outcome fta (reason)      |
  |               |                        | load active templates, decrypt in memory ---->|             |
  |               |                        | score = matcher.score(probe, templates) ------------------->|
  |               |                        | decision = score >= threshold                               |
  |               |                        | (trial mode) insert trial + audit, one transaction --------------->|
  |               |                        | discard image, embedding, decrypted vectors                 |
  |<-- 200 {score, decision, quality} -----|                    |               |              |           |
```

Ordering rules: consent is checked before any image is decoded. Image and vectors are discarded before the response is built. The response never includes an embedding.

## 5. Security and Privacy

### 5.1 Threat model

In scope:
- Accidental disclosure of templates or images.
- A local user who can read the project folder or a backup.
- Unauthorised use of admin functions from the same machine or another device on the LAN.
- Use of the tool for covert identification beyond the study.

Out of scope:
- An attacker with administrator rights on the machine.
- Network adversaries (server is localhost only).
- Hardware or side-channel attacks.

### 5.2 Storage minimisation

- Frames are decoded in memory only. Debug frames are off by default.
- Enrolment persists embeddings only, encrypted. Raw images and landmarks are not stored. Bounding-box size and yaw are stored in `quality_json`.
- Trials store scores and labels only.
- Display names are optional and encrypted.

### 5.3 Encryption at rest

- Templates and display names: Fernet (AES-128-CBC with HMAC-SHA256) via `cryptography`.
- Key: 32-byte key in `BIOMETRIC_LAB_KEY_FILE`, outside `data/`. NTFS ACL restricts it to the current user (set with `icacls`). The app refuses to start if other users can read it.
- Key rotation: MultiFernet.
- Other database content (labels, scores, audit) is plaintext SQLite. Mitigation: Windows device encryption for the drive. SQLCipher is an option but not in base scope.
- Losing the key makes templates unrecoverable. Templates can be re-created by re-enrolment. The README states this.

### 5.4 Consent records

- Consent text is versioned in `docs/`. The SHA-256 of the shown text is stored with each record.
- Consent is per purpose. Withdrawal is one operator action and triggers UC-07.
- Consent records are never deleted, only marked withdrawn.

### 5.5 Logs and redaction

- Access logs: method, path, status, latency, request id. No bodies.
- Logging filter removes base64-like strings longer than 200 characters and keys named `image_b64`, `embedding`, `vector`, `frames`.
- Error responses never echo a payload.

### 5.6 Authentication and web hardening

- Passwords: argon2id.
- Login rate limit: 5 attempts per minute per IP.
- Session cookie: HttpOnly, SameSite=Strict, 30-minute idle timeout.
- CSRF token on all state-changing requests.
- Headers: `Content-Security-Policy: default-src 'self'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Permissions-Policy: camera=(self)`.
- Bind to 127.0.0.1; warning at startup if configured otherwise.
- Limits: body size, image dimensions, image format sniffing, maximum 10 frames per enrolment.

### 5.7 Licences and compliance

- InsightFace weights are for non-commercial research use. Record the licence in `docs/model_licences.md`.
- Ethics approval is a gate before data collection (IMPLEMENTATION_PLAN.md, M13).
- If GDPR or similar applies, a short data protection note goes in `docs/ethics_and_privacy.md`.

## 6. Retention Defaults

| Data | Default | Mechanism |
|---|---|---|
| Templates | Until study end or withdrawal, whichever is first | FR-15, FR-16 |
| Participant record | Until study end | Admin deletion |
| Trials (anonymised after withdrawal) | Study length plus archive period set by ethics approval | Retention settings |
| Debug frames | Off. If on, at most 24 hours | Retention sweep |
| Audit events | Kept for the study period; no biometric content | Hash chain |

## 7. Liveness Boundary

- Identity verification and liveness are separate code paths with separate storage fields.
- The app never reports identity as secure against presentation attacks.
- Liveness results are reported as the output of a named method on study data. APCER and BPCER are reported only if a presentation-attack dataset is collected under the ethics approval.

## 8. Metrics and EER

### 8.1 Scores and decisions

- Embeddings are L2-normalised: e = v / ||v||.
- Cosine similarity: cos(a, b) = a . b, in [-1, 1].
- Verification score against a participant with templates t_1..t_K: s = max over k of cos(p, t_k).
- Decision: **accept if s >= t**. The same rule is used for metrics, sweep and live decisions.

### 8.2 Definitions

G = genuine decided scores g_i. I = impostor decided scores i_j. FTA trials are excluded from all rate denominators.

| Metric | Formula | Notes |
|---|---|---|
| FAR(t) | count(i_j >= t) / \|I\| | Impostor attempts accepted. Equals FMR. |
| FRR(t) | count(g_i < t) / \|G\| | Genuine attempts rejected. Equals FNMR. |
| GAR(t) | 1 - FRR(t) | |
| FTA rate | \|FTA\| / \|all attempts\| | Reported separately |
| Accuracy | (TP + TN) / (\|G\| + \|I\|) | Depends on the class mix; state the ratio |
| Balanced accuracy | (GAR(t) + (1 - FAR(t))) / 2 | Primary summary |
| EER | value where FAR(t) = FRR(t) | Section 8.4 |

FAR(t) is non-increasing and FRR(t) is non-decreasing in t. This is tested.

### 8.3 Confidence intervals

Wilson score interval for p = x/n, with z = 1.96:

```
centre    = (p + z^2/(2n)) / (1 + z^2/n)
halfwidth = z * sqrt( p(1-p)/n + z^2/(4n^2) ) / (1 + z^2/n)
CI        = [centre - halfwidth, centre + halfwidth]
```

Check value: x = 5, n = 10 gives approximately [0.2366, 0.7634].

Rule of three: zero errors in n trials gives a 95% upper bound of about 3/n.

Correlation caveat: trials from the same participant are not independent, so Wilson intervals are optimistic. A subject-level bootstrap (resample participants with replacement, 2000 iterations, percentile interval) is reported alongside and is required, not optional.

### 8.4 EER algorithm

Input: genuine and impostor score arrays, FTA excluded.

1. If either array is empty, return null with reason EMPTY_CLASS.
2. Candidates: T = sorted unique values of G union I, then append max(T) + 1e-9, so FRR reaches 1 and FAR reaches 0.
3. Sort G and I. For each t, count(i >= t) and count(g < t) use binary search (searchsorted). No per-threshold loops over raw data.
4. Let d(t) = FRR(t) - FAR(t). FRR is non-decreasing and FAR non-increasing, so d is non-decreasing. Find the first index k with d(t_k) >= 0.
5. Discrete EER: at t_k, EER_d = (FAR(t_k) + FRR(t_k)) / 2.
6. Interpolated EER: if k > 0 and d(t_k) > 0, with a = d(t_{k-1}) < 0 and b = d(t_k) > 0, let w = -a / (b - a). Then EER_i = FAR(t_{k-1}) + w (FAR(t_k) - FAR(t_{k-1})) and t_EER = t_{k-1} + w (t_k - t_{k-1}). Label this as linear interpolation between operating points.
7. If k = 0, report EER at the lowest threshold with warning CLASSES_NOT_ORDERED.

Both values are shown. The write-up states which one it uses.

### 8.5 Sweep output

FAR(t) and FRR(t) at all candidates, decimated to max_points for display by uniform index sampling (first and last points kept). CSV export is full resolution.

## 9. Test Strategy

### 9.1 Unit tests (no I/O, no model)

**Rates.** G = {0.9, 0.8, 0.4}, I = {0.1, 0.3, 0.5}:
- t = 0.6: FRR = 1/3, FAR = 0.
- t = 0.45: FRR = 1/3, FAR = 1/3.
- t = 0.5 (boundary): FRR = 1/3, FAR = 1/3 (0.5 >= 0.5 is accepted).
- Empty impostor set returns null with EMPTY_CLASS.
- Adding an FTA row changes no rate.

**EER.**
- Example A (G and I above): discrete EER = 1/3 at t = 0.5. At t = 0.4, FAR = 1/3 and FRR = 0. At t = 0.8, FAR = 0 and FRR = 1/3.
- Example B (separable): G = {0.9, 0.8}, I = {0.1, 0.2}: EER = 0.
- Example C (identical distributions): G = I = {0.1, 0.5, 0.9}: EER = 0.5 at the crossing; interpolated value checked to 1e-9 against the hand calculation.
- Symmetry: negating scores and swapping labels gives the same EER.
- Property tests (hypothesis): FAR non-increasing, FRR non-decreasing.

**Wilson.** x = 5, n = 10: [0.2366, 0.7634] to 4 dp. x = 0, n = 100: lower 0, upper about 0.0370. n = 0 returns null.

**Sweep.** Candidate set includes all scores and the sentinel. Curve monotone. Decimation keeps first and last points.

**Cosine and matching.** Identical gives 1, orthogonal gives 0, opposite gives -1. Zero vector raises a typed error, not NaN. Max fusion equals the maximum.

**Quality gate.** Boundaries: det_score 0.6 accepted, 0.59 rejected; min side 80 accepted, 79 rejected; yaw 30 accepted, 30.1 rejected. Two faces give MULTIPLE_FACES.

**Crypto.** Round trip; tampered ciphertext raises; wrong key raises; MultiFernet decrypts old tokens after rotation; key file with broad permissions is refused.

**Redaction.** Long base64 strings and banned keys are removed from log records; normal messages pass.

### 9.2 Integration tests (FakeFaceEngine)

FakeFaceEngine: each synthetic image encodes an identity seed and a noise seed. Identity maps to a fixed random unit vector c; the returned embedding is normalise(c + sigma * noise). With suitable sigma, genuine scores are about 0.8 and impostor scores about 0.0.

- **Consent and enrolment:** no consent gives 409; with consent, 5 frames give 5 templates; a yawed frame is rejected with the right code; withdrawal deletes templates and blocks verification.
- **Verification:** genuine accepted; impostor rejected; threshold override changes decision; no-face image gives FTA; response contains no array-like embedding (schema test).
- **Trials and metrics:** seeded population of 50 identities with 5 frames each gives about 500 genuine and 500 impostor trials. Endpoint metrics equal direct computation from DB rows (exact). Per-tag totals sum to the untagged total.
- **Sweep:** endpoint EER equals direct computation within 1e-9; sweep at operating threshold equals the metrics endpoint.
- **Export:** metadata block present; column allowlist matches; row count equals trial count; no base64 or long float arrays.
- **Retention:** dry run reports counts and deletes nothing; live run removes expired frames and templates; anonymise keeps trials under aliases; purge removes trials.
- **Audit chain:** each mutating route writes exactly one event; verify passes; editing a row in a test copy makes verify fail.
- **Auth:** operator on admin route gives 403; unauthenticated gives 401; missing CSRF gives 403; login rate limit gives 429.
- **End-to-end redaction:** post a base64 image to each image route; captured logs and error bodies must not contain the payload.
- **Migrations:** upgrade head on empty database; downgrade base; upgrade again.

### 9.3 Model tests (marked `model`, run locally)

- Self-test: real engine on the bundled image gives a 512-dimensional embedding (or the fallback's dimension), self-similarity above 0.99, deterministic across two runs.
- Two photos of one person score above a documented reference; two different people score below it. These are sanity checks, not accuracy claims.
- Latency: median and p95 per frame, written to docs/benchmarks.md.

### 9.4 Manual webcam checklist

Kept in IMPLEMENTATION_PLAN.md, section 4. Run once per build before data collection.

## 10. Error Model

| HTTP | When | Example code |
|---|---|---|
| 400 | Malformed JSON or invalid field | VALIDATION_ERROR |
| 401 | Not logged in | NOT_AUTHENTICATED |
| 403 | Wrong role or missing CSRF | FORBIDDEN, CSRF_MISSING |
| 404 | Unknown id | NOT_FOUND |
| 409 | Consent inactive, run closed, deletion conflict | CONSENT_INACTIVE, RUN_CLOSED |
| 413 | Image or body too large | PAYLOAD_TOO_LARGE |
| 422 | Quality or FTA; EMPTY_CLASS for metrics | NO_FACE, EXCESSIVE_YAW, EMPTY_CLASS |
| 429 | Rate limit | RATE_LIMITED |
| 503 | Liveness method unavailable; engine not loaded | LIVENESS_UNAVAILABLE, ENGINE_UNAVAILABLE |

All error bodies follow the problem-details shape in section 3 and never echo request payloads.
