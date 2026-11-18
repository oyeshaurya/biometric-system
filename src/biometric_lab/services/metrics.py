"""Metrics, by-condition breakdown and sweep from stored trials (FR-10, FR-11).

Loads decided trial scores from the database and delegates the mathematics to the pure
``core.metrics`` functions, so endpoint values equal a direct computation (tested).
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from biometric_lab.core.metrics.rates import rate_report
from biometric_lab.core.metrics.sweep import threshold_sweep
from biometric_lab.core.metrics.wilson import rule_of_three_upper, wilson_interval
from biometric_lab.db.models import Run, Trial


class MetricsError(Exception):
    pass


def _ci(x: int, n: int) -> list[float] | None:
    interval = wilson_interval(x, n)
    return None if interval is None else [interval[0], interval[1]]


class MetricsService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _run(self, run_id: int) -> Run:
        run = self.session.get(Run, run_id)
        if run is None or run.status == "deleted":
            raise MetricsError(f"run {run_id} not found")
        return run

    def _trials(self, run_id: int) -> list[Trial]:
        return list(
            self.session.execute(select(Trial).where(Trial.run_id == run_id)).scalars()
        )

    @staticmethod
    def _split(
        trials: list[Trial], tag: str | None
    ) -> tuple[list[float], list[float], int]:
        genuine: list[float] = []
        impostor: list[float] = []
        n_fta = 0
        for t in trials:
            if tag is not None and tag not in (t.condition_tags or []):
                continue
            if t.outcome == "fta" or t.score is None:
                n_fta += 1
                continue
            if t.ground_truth == "genuine":
                genuine.append(float(t.score))
            else:
                impostor.append(float(t.score))
        return genuine, impostor, n_fta

    def report(
        self, run_id: int, *, threshold: float | None = None, tag: str | None = None
    ) -> dict:
        run = self._run(run_id)
        thr = run.threshold_snapshot if threshold is None else float(threshold)
        genuine, impostor, n_fta = self._split(self._trials(run_id), tag)

        rr = rate_report(genuine, impostor, thr)
        n_g, n_i = len(genuine), len(impostor)
        false_accepts = int(np.count_nonzero(np.asarray(impostor) >= thr)) if n_i else 0
        false_rejects = int(np.count_nonzero(np.asarray(genuine) < thr)) if n_g else 0

        warnings = list(rr.warnings)
        if n_i and false_accepts == 0:
            bound = rule_of_three_upper(n_i)
            if bound is not None and bound > 0.01:
                warnings.append("FAR_ZERO_WIDE_BOUND")

        total_attempts = n_g + n_i + n_fta
        return {
            "run_id": run_id,
            "threshold": thr,
            "n_genuine": n_g,
            "n_impostor": n_i,
            "n_fta": n_fta,
            "fta_rate": (n_fta / total_attempts) if total_attempts else None,
            "far": rr.far,
            "far_ci95": _ci(false_accepts, n_i),
            "frr": rr.frr,
            "frr_ci95": _ci(false_rejects, n_g),
            "gar": rr.gar,
            "gar_ci95": (
                None
                if _ci(false_rejects, n_g) is None
                else [1 - _ci(false_rejects, n_g)[1], 1 - _ci(false_rejects, n_g)[0]]
            ),
            "accuracy": rr.accuracy,
            "balanced_accuracy": rr.balanced_accuracy,
            "model": {"name": run.model_name, "version": run.model_version},
            "warnings": warnings,
        }

    def by_condition(self, run_id: int, *, threshold: float | None = None) -> dict:
        run = self._run(run_id)
        thr = run.threshold_snapshot if threshold is None else float(threshold)
        trials = self._trials(run_id)

        tags: set[str] = set()
        for t in trials:
            tags.update(t.condition_tags or [])

        rows = []
        for tag in sorted(tags):
            genuine, impostor, _ = self._split(trials, tag)
            rr = rate_report(genuine, impostor, thr)
            rows.append(
                {
                    "tag": tag,
                    "n_genuine": len(genuine),
                    "n_impostor": len(impostor),
                    "far": rr.far,
                    "frr": rr.frr,
                    "gar": rr.gar,
                    "accuracy": rr.accuracy,
                }
            )

        untagged_g, untagged_i = [], []
        for t in trials:
            if t.condition_tags:
                continue
            if t.outcome == "fta" or t.score is None:
                continue
            (untagged_g if t.ground_truth == "genuine" else untagged_i).append(float(t.score))
        untagged_rr = rate_report(untagged_g, untagged_i, thr)
        return {
            "run_id": run_id,
            "threshold": thr,
            "rows": rows,
            "untagged": {
                "n_genuine": len(untagged_g),
                "n_impostor": len(untagged_i),
                "far": untagged_rr.far,
                "frr": untagged_rr.frr,
                "gar": untagged_rr.gar,
                "accuracy": untagged_rr.accuracy,
            },
        }

    def sweep(
        self, run_id: int, *, tag: str | None = None, max_points: int = 1000
    ) -> dict:
        run = self._run(run_id)
        genuine, impostor, _ = self._split(self._trials(run_id), tag)
        result = threshold_sweep(genuine, impostor, max_points=max_points)
        payload = result.as_dict()
        payload["run_id"] = run_id
        payload["operating_threshold"] = run.threshold_snapshot
        return payload

    def subject_bootstrap(
        self,
        run_id: int,
        *,
        threshold: float | None = None,
        iterations: int = 2000,
        seed: int = 12345,
    ) -> dict:
        """Subject-level bootstrap CIs for FAR and FRR (required reporting, SYSTEM_DESIGN 8.3).

        Resamples *participants* (by label) with replacement, so correlated repeats within a
        participant are respected, unlike the trial-level Wilson interval.
        """
        run = self._run(run_id)
        thr = run.threshold_snapshot if threshold is None else float(threshold)
        trials = [t for t in self._trials(run_id) if t.outcome != "fta" and t.score is not None]

        genuine_by_subject: dict[str, list[float]] = defaultdict(list)
        impostor_by_subject: dict[str, list[float]] = defaultdict(list)
        for t in trials:
            if t.ground_truth == "genuine":
                genuine_by_subject[t.claimed_label].append(float(t.score))
            else:
                impostor_by_subject[t.probe_label].append(float(t.score))

        g_subjects = list(genuine_by_subject)
        i_subjects = list(impostor_by_subject)
        if not g_subjects or not i_subjects:
            return {"far_ci95": None, "frr_ci95": None, "iterations": 0}

        rng = np.random.default_rng(seed)
        far_samples = np.empty(iterations)
        frr_samples = np.empty(iterations)
        for b in range(iterations):
            gi = rng.integers(0, len(i_subjects), len(i_subjects))
            gg = rng.integers(0, len(g_subjects), len(g_subjects))
            imp = [s for idx in gi for s in impostor_by_subject[i_subjects[idx]]]
            gen = [s for idx in gg for s in genuine_by_subject[g_subjects[idx]]]
            imp_arr = np.asarray(imp)
            gen_arr = np.asarray(gen)
            far_samples[b] = np.mean(imp_arr >= thr) if imp_arr.size else np.nan
            frr_samples[b] = np.mean(gen_arr < thr) if gen_arr.size else np.nan

        def pct(arr: np.ndarray) -> list[float]:
            clean = arr[~np.isnan(arr)]
            return [float(np.percentile(clean, 2.5)), float(np.percentile(clean, 97.5))]

        return {
            "threshold": thr,
            "far_ci95": pct(far_samples),
            "frr_ci95": pct(frr_samples),
            "iterations": iterations,
            "n_genuine_subjects": len(g_subjects),
            "n_impostor_subjects": len(i_subjects),
        }
