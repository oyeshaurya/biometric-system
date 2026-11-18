# Model Licences and Provenance

Record here the exact model weights used, their source and their licence, before any
participant data is collected (decision D-5 in the PRD).

## Identity engine options

| Engine | Detector + recogniser | Dim | Source | Licence notes |
|---|---|---|---|---|
| `insightface` (primary) | RetinaFace + ArcFace (`buffalo_l`) | 512 | InsightFace model zoo | Pretrained weights are published for **non-commercial research use**. Read and record the exact licence text for the downloaded pack. Suitable for an academic study; not for commercial deployment. |
| `yunet_sface` (fallback) | YuNet + SFace | 128 | OpenCV Zoo | Apache-2.0 / MIT-style per the OpenCV Zoo entries; verify the specific files. Pip-installable on Windows with no compilation, so this is the fallback if InsightFace will not install (risk R1). |
| `fake` (tests/dev) | deterministic synthetic | 128 | this repository | MIT (part of this project). Not a real model; for tests, UI development and synthetic demo runs only. |

## How to record provenance

For the engine actually used in the study, fill in:

- Model pack name and version, and the download URL.
- SHA-256 checksums of each weight file placed under `models/`.
- The licence text or a link, and the date it was read.
- Any usage restrictions relevant to the study (non-commercial, attribution, redistribution).

The application records the model name and version on every trial and in every export, so
results are always traceable to the engine that produced them (FR-19).

## Status

Not yet filled in. The project defaults to the `fake` engine (MIT, in this repo). Select a
real engine with `BIOMETRIC_LAB_ENGINE` and `pip install -e ".[engine]"`, then complete the
table above.
