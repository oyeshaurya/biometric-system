"""Real face engines (M0/M3). Heavy dependencies are imported lazily.

Install with ``pip install -e ".[engine]"``. InsightFace pretrained weights are for
non-commercial research use; record the licence in ``docs/model_licences.md``.

These classes raise :class:`FaceEngineError` with a clear message when the optional
libraries or model weights are not available, so the rest of the app degrades cleanly.
"""

from __future__ import annotations

import numpy as np

from biometric_lab.core.face.base import FaceDetection, FaceEngineError, ModelInfo


def _estimate_yaw(landmarks: np.ndarray) -> float:
    """Rough yaw from 5-point landmarks: eye-to-nose horizontal asymmetry, in degrees.

    landmarks order (InsightFace): left eye, right eye, nose, left mouth, right mouth.
    This is a coarse proxy, adequate for a quality gate, not a pose estimator.
    """
    left_eye, right_eye, nose = landmarks[0], landmarks[1], landmarks[2]
    eye_mid_x = (left_eye[0] + right_eye[0]) / 2.0
    eye_width = abs(right_eye[0] - left_eye[0]) + 1e-6
    offset = (nose[0] - eye_mid_x) / eye_width  # ~0 frontal, +/- when turned
    return float(np.clip(offset * 90.0, -90.0, 90.0))


class InsightFaceEngine:
    """InsightFace buffalo_l (RetinaFace detector + ArcFace recogniser, 512-d)."""

    def __init__(self, model_name: str = "buffalo_l", det_size: int = 640) -> None:
        try:
            from insightface.app import FaceAnalysis
        except Exception as exc:  # noqa: BLE001
            raise FaceEngineError(
                "insightface is not installed. Run: pip install -e \".[engine]\""
            ) from exc
        try:
            self._app = FaceAnalysis(name=model_name)
            self._app.prepare(ctx_id=-1, det_size=(det_size, det_size))  # ctx_id=-1 -> CPU
        except Exception as exc:  # noqa: BLE001
            raise FaceEngineError(f"failed to load InsightFace model '{model_name}'") from exc
        self.info: ModelInfo = {
            "detector": "RetinaFace",
            "recogniser": "ArcFace",
            "model_name": model_name,
            "model_version": "insightface-0.7",
            "dim": 512,
        }

    def analyse(self, image_bgr: np.ndarray) -> list[FaceDetection]:
        faces = self._app.get(image_bgr)
        out: list[FaceDetection] = []
        for f in faces:
            x1, y1, x2, y2 = f.bbox
            emb = np.asarray(f.normed_embedding, dtype=np.float32)
            out.append(
                FaceDetection(
                    bbox=(float(x1), float(y1), float(x2 - x1), float(y2 - y1)),
                    det_score=float(f.det_score),
                    yaw_deg=_estimate_yaw(np.asarray(f.kps)),
                    embedding=emb,
                )
            )
        return out


class YuNetSFaceEngine:
    """Fallback: OpenCV Zoo YuNet (detector) + SFace (recogniser), 128-d.

    Requires the two ONNX model files under ``models/``; paths are read from env or the
    default ``models/`` folder. Raises if OpenCV or the weights are missing.
    """

    def __init__(
        self,
        detector_path: str = "models/face_detection_yunet.onnx",
        recogniser_path: str = "models/face_recognition_sface.onnx",
    ) -> None:
        try:
            import cv2
        except Exception as exc:  # noqa: BLE001
            raise FaceEngineError(
                "opencv is not installed. Run: pip install -e \".[engine]\""
            ) from exc
        import os

        if not os.path.exists(detector_path) or not os.path.exists(recogniser_path):
            raise FaceEngineError(
                "YuNet/SFace ONNX weights not found under models/. See docs/model_licences.md"
            )
        self._cv2 = cv2
        self._detector = cv2.FaceDetectorYN.create(detector_path, "", (320, 320))
        self._recogniser = cv2.FaceRecognizerSF.create(recogniser_path, "")
        self.info: ModelInfo = {
            "detector": "YuNet",
            "recogniser": "SFace",
            "model_name": "yunet_sface",
            "model_version": "opencv-zoo",
            "dim": 128,
        }

    def analyse(self, image_bgr: np.ndarray) -> list[FaceDetection]:
        h, w = image_bgr.shape[:2]
        self._detector.setInputSize((w, h))
        _, faces = self._detector.detect(image_bgr)
        out: list[FaceDetection] = []
        if faces is None:
            return out
        for row in faces:
            x, y, bw, bh = row[0], row[1], row[2], row[3]
            score = float(row[-1])
            aligned = self._recogniser.alignCrop(image_bgr, row)
            feat = self._recogniser.feature(aligned).flatten().astype(np.float32)
            feat = feat / (np.linalg.norm(feat) + 1e-9)
            # YuNet landmarks start at index 4: re, le, nose, rm, lm (x,y pairs)
            kps = np.array(
                [[row[4], row[5]], [row[6], row[7]], [row[8], row[9]]], dtype=np.float32
            )
            out.append(
                FaceDetection(
                    bbox=(float(x), float(y), float(bw), float(bh)),
                    det_score=score,
                    yaw_deg=_estimate_yaw(kps),
                    embedding=feat,
                )
            )
        return out
