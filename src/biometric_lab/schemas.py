"""Pydantic request models for the API (SYSTEM_DESIGN.md section 3).

Responses are returned as plain dicts built by the services, so no biometric field can
leak through an over-broad response model.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class ParticipantCreate(BaseModel):
    subject_code: str = Field(min_length=1, max_length=32)
    display_name: str | None = None


class ConsentCreate(BaseModel):
    consent_version: str
    consent_text_sha256: str = Field(min_length=64, max_length=64)
    purposes: list[str]
    accepted: bool


class ReasonRequest(BaseModel):
    reason: str = Field(min_length=1)


class FrameIn(BaseModel):
    image_b64: str


class EnrolRequest(BaseModel):
    frames: list[FrameIn] = Field(min_length=1, max_length=10)
    replace: bool = False


class VerifyRequest(BaseModel):
    claimed_participant_id: int
    image_b64: str
    threshold: float | None = None
    liveness: bool = False


class PreviewRequest(BaseModel):
    image_b64: str


class RunCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None


class ConfirmRequest(BaseModel):
    confirm: str


class TrialCreate(BaseModel):
    probe_label: str = Field(min_length=1, max_length=64)
    claimed_label: str = Field(min_length=1, max_length=64)
    image_b64: str
    condition_tags: list[str] = Field(default_factory=list)
    ground_truth_hint: str | None = None
    liveness: bool = False


class SettingUpdate(BaseModel):
    value: object
    reason: str = Field(min_length=1)


class OperatorCreate(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8)
    role: str = "operator"


class LivenessRequest(BaseModel):
    image_b64: str
    trial_id: int | None = None
