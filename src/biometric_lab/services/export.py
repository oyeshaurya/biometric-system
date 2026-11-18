"""CSV export with a metadata block and a strict column allowlist (FR-13).

No embeddings, images or landmarks are ever written. Each file begins with ``#``-prefixed
metadata lines (run, threshold, model, app version, timestamp).
"""

from __future__ import annotations

import csv
import io

from sqlalchemy import select
from sqlalchemy.orm import Session

from biometric_lab import __version__
from biometric_lab.db.models import Run, Trial, utcnow
from biometric_lab.services.audit import AuditService
from biometric_lab.services.metrics import MetricsService

TRIAL_COLUMNS = [
    "id",
    "run_id",
    "probe_label",
    "claimed_label",
    "ground_truth",
    "outcome",
    "score",
    "threshold",
    "fta_reason",
    "template_count",
    "condition_tags",
    "model_name",
    "model_version",
    "liveness_method",
    "liveness_score",
    "liveness_passed",
    "duration_ms",
    "created_at",
]


class ExportError(Exception):
    pass


class ExportService:
    def __init__(self, session: Session, audit: AuditService, metrics: MetricsService) -> None:
        self.session = session
        self.audit = audit
        self.metrics = metrics

    def _run(self, run_id: int) -> Run:
        run = self.session.get(Run, run_id)
        if run is None or run.status == "deleted":
            raise ExportError(f"run {run_id} not found")
        return run

    def _header(self, run: Run, extra: dict | None = None) -> list[str]:
        lines = [
            f"# run_id={run.id}",
            f"# run_name={run.name}",
            f"# threshold={run.threshold_snapshot}",
            f"# model={run.model_name}:{run.model_version}",
            f"# app_version={__version__}",
            f"# exported_at={utcnow().isoformat()}",
        ]
        for key, value in (extra or {}).items():
            lines.append(f"# {key}={value}")
        return lines

    def trials_csv(self, run_id: int, *, actor_id: int | None = None) -> str:
        run = self._run(run_id)
        trials = list(
            self.session.execute(
                select(Trial).where(Trial.run_id == run_id).order_by(Trial.id)
            ).scalars()
        )
        buf = io.StringIO()
        for line in self._header(run):
            buf.write(line + "\n")
        writer = csv.DictWriter(buf, fieldnames=TRIAL_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for t in trials:
            writer.writerow(
                {
                    "id": t.id,
                    "run_id": t.run_id,
                    "probe_label": t.probe_label,
                    "claimed_label": t.claimed_label,
                    "ground_truth": t.ground_truth,
                    "outcome": t.outcome,
                    "score": t.score,
                    "threshold": t.threshold,
                    "fta_reason": t.fta_reason or "",
                    "template_count": t.template_count,
                    "condition_tags": ";".join(t.condition_tags or []),
                    "model_name": t.model_name,
                    "model_version": t.model_version,
                    "liveness_method": t.liveness_method or "",
                    "liveness_score": t.liveness_score if t.liveness_score is not None else "",
                    "liveness_passed": "" if t.liveness_passed is None else t.liveness_passed,
                    "duration_ms": t.duration_ms,
                    "created_at": t.created_at.isoformat() if t.created_at else "",
                }
            )
        self.audit.append(
            "export.trials",
            actor_id=actor_id,
            entity_type="run",
            entity_id=run_id,
            summary={"rows": len(trials)},
        )
        return buf.getvalue()

    def metrics_csv(
        self, run_id: int, *, tag: str | None = None, actor_id: int | None = None
    ) -> str:
        run = self._run(run_id)
        data = self.metrics.by_condition(run_id)
        buf = io.StringIO()
        for line in self._header(run, {"export": "per_condition_metrics"}):
            buf.write(line + "\n")
        writer = csv.writer(buf)
        writer.writerow(["tag", "n_genuine", "n_impostor", "far", "frr", "gar", "accuracy"])
        for row in data["rows"]:
            writer.writerow(
                [row["tag"], row["n_genuine"], row["n_impostor"], row["far"], row["frr"],
                 row["gar"], row["accuracy"]]
            )
        u = data["untagged"]
        writer.writerow(
            ["(untagged)", u["n_genuine"], u["n_impostor"], u["far"], u["frr"], u["gar"],
             u["accuracy"]]
        )
        self.audit.append(
            "export.metrics",
            actor_id=actor_id,
            entity_type="run",
            entity_id=run_id,
            summary={"rows": len(data["rows"]) + 1},
        )
        return buf.getvalue()

    def sweep_csv(
        self, run_id: int, *, tag: str | None = None, actor_id: int | None = None
    ) -> str:
        run = self._run(run_id)
        data = self.metrics.sweep(run_id, tag=tag, max_points=0)  # full resolution
        buf = io.StringIO()
        for line in self._header(run, {"export": "sweep", "tag": tag or ""}):
            buf.write(line + "\n")
        writer = csv.writer(buf)
        writer.writerow(["threshold", "far", "frr"])
        curve = data["curve"]
        for thr, far, frr in zip(curve["thresholds"], curve["far"], curve["frr"], strict=True):
            writer.writerow([thr, far, frr])
        self.audit.append(
            "export.sweep",
            actor_id=actor_id,
            entity_type="run",
            entity_id=run_id,
            summary={"rows": len(curve["thresholds"])},
        )
        return buf.getvalue()
