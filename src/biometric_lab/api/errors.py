"""RFC 7807 problem responses and exception mapping (SYSTEM_DESIGN.md section 10)."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from biometric_lab.core.face.base import FaceEngineError
from biometric_lab.core.liveness.base import LivenessUnavailable
from biometric_lab.core.matching.base import MatchError
from biometric_lab.core.security.crypto import CryptoError
from biometric_lab.imaging import ImageDecodeError
from biometric_lab.services.auth import AdminProtected, AuthError, RateLimited
from biometric_lab.services.enrolment import EnrolmentError
from biometric_lab.services.participants import ConsentInactive, NotFound, ParticipantError
from biometric_lab.services.settings import SettingsError
from biometric_lab.services.trials import RunError


class ProblemError(Exception):
    def __init__(self, status: int, code: str, detail: str, title: str | None = None) -> None:
        self.status = status
        self.code = code
        self.detail = detail
        self.title = title or code
        super().__init__(detail)


def problem(status: int, code: str, detail: str, title: str | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "type": "about:blank",
            "title": title or code,
            "status": status,
            "detail": detail,
            "code": code,
        },
    )


_EXCEPTION_MAP: dict[type[Exception], tuple[int, str]] = {
    NotFound: (404, "NOT_FOUND"),
    ParticipantError: (400, "PARTICIPANT_ERROR"),
    ConsentInactive: (409, "CONSENT_INACTIVE"),
    EnrolmentError: (422, "ENROLMENT_ERROR"),
    RunError: (409, "RUN_ERROR"),
    SettingsError: (400, "SETTINGS_ERROR"),
    AuthError: (401, "NOT_AUTHENTICATED"),
    RateLimited: (429, "RATE_LIMITED"),
    AdminProtected: (409, "ADMIN_PROTECTED"),
    ImageDecodeError: (400, "IMAGE_DECODE_ERROR"),
    MatchError: (422, "MATCH_ERROR"),
    CryptoError: (500, "CRYPTO_ERROR"),
    FaceEngineError: (503, "ENGINE_UNAVAILABLE"),
    LivenessUnavailable: (503, "LIVENESS_UNAVAILABLE"),
}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProblemError)
    async def _problem_handler(_request: Request, exc: ProblemError) -> JSONResponse:
        return problem(exc.status, exc.code, exc.detail, exc.title)

    for exc_type, (status, code) in _EXCEPTION_MAP.items():

        async def _handler(_request: Request, exc: Exception, _status=status, _code=code) -> JSONResponse:
            return problem(_status, _code, str(exc))

        app.add_exception_handler(exc_type, _handler)
