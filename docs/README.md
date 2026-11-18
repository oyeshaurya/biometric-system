# Face-Recognition Performance Lab: Specification Pack

This folder is the complete specification for the project. It is written so an implementer can build the system without further input, apart from the open decisions listed in the PRD.

## Read in this order

| # | Document | What it answers |
|---|---|---|
| 1 | [PRD.md](PRD.md) | What we are building, why, for whom, and what counts as success. Lists requirements FR-01..FR-22 and NFR-01..NFR-14. |
| 2 | [USE_CASES.md](USE_CASES.md) | How each actor uses the system: UC-01..UC-10 with main and alternate flows. |
| 3 | [FEATURES.md](FEATURES.md) | The feature list, grouped in 10 epics, with priorities and traceability. |
| 4 | [ARCHITECTURE.md](ARCHITECTURE.md) | Layers, components, interfaces, folder layout, technology choices, architectural decisions. |
| 5 | [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md) | Data model, REST API, verification sequence, security and privacy, metric formulas and EER algorithm, test strategy, error model. |
| 6 | [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) | Milestones M0 to M13 with tasks and exit criteria, manual webcam checklist, risks, definition of done. |

## Traceability

- Requirement IDs (FR-, NFR-) are defined in the PRD and referenced by use cases, features, design and milestones.
- Use case IDs (UC-) are defined in USE_CASES.md and referenced by features and milestones.
- Feature IDs (F-) are defined in FEATURES.md and referenced by milestones.
- Decisions (AD-) are in ARCHITECTURE.md. Open decisions (D-) are in the PRD and IMPLEMENTATION_PLAN.md.

## Before any participant data is collected

1. Ethics approval (decision D-1).
2. Data protection regime confirmed (D-2).
3. Sample sizes set (D-3).
4. Liveness scope decided (D-4).
5. Model fallback accepted if needed (D-5).

## Scope in one paragraph

A local, single-machine web app. An operator enrols consenting participants with a webcam, runs 1:1 face-verification trials under labelled conditions, and the system computes FAR, FRR, GAR, EER and threshold sweeps with confidence intervals. Results export as CSV without biometric content. Consent, withdrawal, retention and an audit trail are built in. Liveness is optional and kept separate from identity matching.

## Out of scope

1:N identification, multi-biometric fusion, public hosting, mobile apps, and any security claim against presentation attacks beyond what is measured on study data.
