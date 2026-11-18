# Use Cases

**Traces to:** PRD.md (FR-, NFR-). **Used by:** FEATURES.md, SYSTEM_DESIGN.md, IMPLEMENTATION_PLAN.md.

Actors: **Operator**, **Admin**, **Analyst** (read-only, treated as Operator in v1), **Participant** (not a system user).

---

## UC-01 Enrol a participant

- **Actors:** Operator (primary), Participant.
- **Preconditions:** Operator logged in. Participant has read the consent text. Webcam available.
- **Trigger:** Operator starts enrolment for a participant.
- **Main flow:**
  1. Operator creates a participant with a subject code. (FR-02)
  2. System shows consent text and version. Participant accepts. System stores consent record (hash of text, purposes, timestamp). (FR-01)
  3. Operator starts enrolment. Capture page shows live guidance overlay. (NFR-09)
  4. Browser captures frames and posts each to the enrolment endpoint.
  5. System runs quality gate and embedding per frame; stores accepted templates encrypted. (FR-03, FR-03a)
  6. System reports accepted count and rejected frames with reasons.
  7. Audit events written. (FR-17)
- **Alternate flows:**
  - A1 Consent declined: enrolment blocked; no capture occurs.
  - A2 Quality rejections: operator sees reasons ("turn face to camera") and recaptures. Fewer than 3 accepted templates blocks completion.
  - A3 Re-enrolment: old templates soft-deleted and audited first. (FR-20)
  - A4 Camera permission denied: explanation shown; no capture attempted.
- **Postconditions:** Participant has 3 to 10 active encrypted templates; consent record exists; audit events recorded.

## UC-02 Verify (1:1)

- **Actors:** Operator, Participant.
- **Preconditions:** Participant enrolled with active consent and at least one template. Operating threshold set.
- **Main flow:**
  1. Operator selects the claimed participant.
  2. Browser captures one frame and posts it with the claimed participant.
  3. System checks consent, runs quality gate, embeds the probe, scores against all active templates (max cosine similarity), applies threshold. (FR-05)
  4. System returns score, threshold, decision and quality summary. No embedding is returned.
  5. Audit records a summary.
- **Alternate flows:**
  - A1 No face or poor quality: FTA response with reason code; no decision. (FR-09)
  - A2 Consent inactive: refused (409); refusal audited.
  - A3 Liveness requested: liveness result returned separately; identity decision unchanged. (FR-14)
  - A4 Analysis threshold supplied: decision computed at that threshold and flagged non-operational.
- **Postconditions:** No biometric data stored by this use case beyond the audit summary.

## UC-03 Run a trial

- **Actors:** Operator.
- **Preconditions:** Run exists and is open. Probe and claimed participants exist (probe may be an unenrolled subject, recorded by label only).
- **Main flow:**
  1. Operator opens the run and selects probe, claimed participant and condition tags from the controlled vocabulary (lighting, distance, glasses, pose, expression, background, camera).
  2. System shows the ground truth derived from labels (read-only). (FR-08a)
  3. Operator captures and submits. System performs UC-02 and writes the trial row and audit event in one transaction. (NFR-11)
  4. Result shown: outcome, score, threshold.
- **Alternate flows:**
  - A1 Client sends a ground-truth hint that disagrees: server value stored; warning returned. (FR-08a)
  - A2 Probe not enrolled: allowed; trial stored with probe label and no probe participant link.
  - A3 Run closed: refused (409).
  - A4 Batch mode: several frames for the same probe and claimed pair; each frame is its own trial.
  - A5 FTA: trial stored with outcome fta and reason. (FR-09)
- **Postconditions:** Trial exists in the run with full metadata.

## UC-04 Analyse metrics

- **Actors:** Operator, Analyst.
- **Preconditions:** Run has at least one decided genuine trial and one decided impostor trial.
- **Main flow:**
  1. User selects run, threshold (default: run's snapshot) and optional condition tag.
  2. System computes FAR, FRR, GAR, accuracy, balanced accuracy, counts, FTA rate and Wilson intervals. (FR-10)
  3. Per-tag breakdown shown.
  4. Warnings shown for small samples (fewer than 30 per class, or rule-of-three upper bound above 1%).
- **Alternate flows:**
  - A1 One class empty: affected metrics shown as not available with reason EMPTY_CLASS.
  - A2 Tag with no trials: row omitted with a note.

## UC-05 Sweep threshold

- **Actors:** Analyst.
- **Preconditions:** As UC-04.
- **Main flow:**
  1. User selects run and optional tag.
  2. System computes FAR(t) and FRR(t) over candidate thresholds. (FR-11, SYSTEM_DESIGN.md section 8)
  3. System returns the curve, discrete EER, interpolated EER, EER threshold and operating threshold.
  4. UI plots the curve with operating threshold and EER marked. (FR-12)
- **Alternate flows:**
  - A1 Very large run: curve decimated for display; export is full resolution.
  - A2 Empty class: refused with explanation (422).

## UC-06 Export

- **Actors:** Analyst.
- **Preconditions:** Run exists.
- **Main flow:**
  1. User chooses export type: trials, per-condition metrics, or sweep.
  2. System writes CSV with metadata block and column allowlist. (FR-13)
  3. Audit records the export (type, run id, row count).
- **Alternate flows:**
  - A1 Trials of withdrawn participants: exported under aliases only, never names or raw subject codes. (FR-15)

## UC-07 Withdraw consent and delete data

- **Actors:** Admin (performs the action on the participant's request, which the operator records).
- **Preconditions:** Admin logged in.
- **Main flow (withdrawal):**
  1. Admin opens participant and chooses Withdraw consent, with reason.
  2. System records withdrawal time, deletes all templates, and blocks enrolment and verification for the participant. (FR-04)
  3. Trials remain for analysis under the chosen mode (anonymise or purge). (FR-15)
  4. Audit records the action with no biometric content.
- **Alternate flows:**
  - A1 Delete a run: admin confirms by typing the run name; all trials in the run are removed; audit keeps run id and count.
  - A2 Retention sweep: scheduled or manual; deletes expired debug frames and templates past retention. (FR-16)
  - A3 Deletion requested while a trial is in progress: trial is refused (409).

## UC-08 Admin configuration

- **Actors:** Admin.
- **Main flow:**
  1. Admin views settings: operating threshold, quality-gate parameters, condition-tag vocabulary, retention periods, debug-frame toggle, liveness enable flag.
  2. Every change requires a reason and is audited with old and new values. (FR-06, FR-17)
  3. Admin creates or disables operator accounts and changes own password. (FR-18)
- **Alternate flows:**
  - A1 Threshold outside [-1, 1]: refused.
  - A2 Debug-frame expiry above 24 hours: refused. (FR-22)
  - A3 Disabling the last admin account: refused.

## UC-09 Liveness check (optional)

- **Actors:** Operator.
- **Preconditions:** Liveness enabled in settings; a method is configured.
- **Main flow:** Operator runs liveness on a frame. System returns method, score, pass flag and reason. Result stored in the trial's liveness fields.
- **Alternate flows:**
  - A1 Method unavailable: 503 with explanation; trial still recorded with liveness marked not run.
  - A2 Liveness result never changes the identity decision. The analysis page shows identity outcomes with and without liveness gating as separate, labelled series.

## UC-10 Review the audit trail

- **Actors:** Admin.
- **Main flow:** Admin opens the audit viewer, filters by action and date, and runs chain verification. The system reports whether the hash chain is intact.
- **Alternate flows:**
  - A1 Chain broken: report the first broken event id; the application stays usable but shows a warning on every admin page.

---

## Use Case to Requirement Map

| Use case | Requirements |
|---|---|
| UC-01 | FR-01, FR-02, FR-03, FR-03a, FR-17, FR-20, NFR-09, NFR-13 |
| UC-02 | FR-01, FR-05, FR-09, FR-14, FR-17, NFR-02 |
| UC-03 | FR-07, FR-08, FR-08a, FR-09, NFR-03, NFR-11 |
| UC-04 | FR-10, FR-19 |
| UC-05 | FR-11, FR-12 |
| UC-06 | FR-13, FR-15, FR-17 |
| UC-07 | FR-04, FR-15, FR-16, FR-17 |
| UC-08 | FR-06, FR-17, FR-18, FR-22 |
| UC-09 | FR-14 |
| UC-10 | FR-17, NFR-11 |
