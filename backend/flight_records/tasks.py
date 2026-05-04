from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from django.db import close_old_connections
from django.utils import timezone

from .models import AnalysisJob, FlightRecord
from .services import apply_analysis, parse_log_file

logger = logging.getLogger(__name__)
executor = ThreadPoolExecutor(max_workers=2)


def _run_analysis_job(job_id):
    close_old_connections()
    try:
        job = AnalysisJob.objects.select_related("flight_record").get(pk=job_id)
        job.status = AnalysisJob.Status.RUNNING
        job.started_at = timezone.now()
        job.error_message = ""
        job.save(update_fields=["status", "started_at", "error_message"])

        record = job.flight_record
        parsed = parse_log_file(Path(record.source_file.path))
        apply_analysis(record, parsed)

        job.status = AnalysisJob.Status.SUCCEEDED
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "finished_at"])
    except Exception as exc:
        logger.exception("Analysis job failed: %s", job_id)
        AnalysisJob.objects.filter(pk=job_id).update(
            status=AnalysisJob.Status.FAILED,
            error_message=str(exc),
            finished_at=timezone.now(),
        )
        FlightRecord.objects.filter(analysis_job__id=job_id).update(
            status=FlightRecord.Status.ANALYSIS_FAILED,
            analysis_error=str(exc),
        )
    finally:
        close_old_connections()


def dispatch_analysis_job(job_id):
    executor.submit(_run_analysis_job, job_id)
