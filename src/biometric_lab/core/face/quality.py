"""Quality gate (FR-03a, SYSTEM_DESIGN.md section 9.1 boundaries).

Accept only: exactly one face; det_score >= min; min face side >= min px; |yaw| <= max.
Boundary behaviour: det_score 0.6 and 0.59 -> accept/reject; side 80 and 79 -> accept/reject;
yaw 30.0 and 30.1 -> accept/reject.
"""

from __future__ import annotations

from dataclasses import dataclass

from biometric_lab.core.face.base import FaceDetection

NO_FACE = "NO_FACE"
MULTIPLE_FACES = "MULTIPLE_FACES"
LOW_DET_SCORE = "LOW_DET_SCORE"
FACE_TOO_SMALL = "FACE_TOO_SMALL"
EXCESSIVE_YAW = "EXCESSIVE_YAW"


@dataclass(frozen=True)
class QualityResult:
    ok: bool
    reason: str | None
    detection: FaceDetection | None

    def guidance(self) -> list[str]:
        """Human hints for the capture overlay."""
        hints = {
            NO_FACE: ["no_face"],
            MULTIPLE_FACES: ["one_face_only"],
            LOW_DET_SCORE: ["improve_lighting"],
            FACE_TOO_SMALL: ["move_closer"],
            EXCESSIVE_YAW: ["face_the_camera"],
        }
        if self.ok:
            return ["ok"]
        return hints.get(self.reason or "", ["retry"])


def check_quality(
    detections: list[FaceDetection],
    *,
    min_det_score: float,
    min_face_px: int,
    max_yaw_deg: float,
) -> QualityResult:
    if len(detections) == 0:
        return QualityResult(False, NO_FACE, None)
    if len(detections) > 1:
        return QualityResult(False, MULTIPLE_FACES, None)
    d = detections[0]
    if d.det_score < min_det_score:
        return QualityResult(False, LOW_DET_SCORE, d)
    if d.min_side_px < min_face_px:
        return QualityResult(False, FACE_TOO_SMALL, d)
    if abs(d.yaw_deg) > max_yaw_deg:
        return QualityResult(False, EXCESSIVE_YAW, d)
    return QualityResult(True, None, d)
