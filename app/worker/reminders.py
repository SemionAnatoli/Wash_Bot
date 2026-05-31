import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import repositories
from app.services.reminder_delivery import ReminderDeliveryService, ReminderMessageGateway

DEFAULT_BATCH_SIZE = 50
DEFAULT_RECLAIM_AFTER = timedelta(minutes=5)


@dataclass(frozen=True, slots=True)
class ReminderProcessingResult:
    selected: int = 0
    claimed: int = 0
    claim_missed: int = 0
    sent: int = 0
    skipped: int = 0
    failed: int = 0
    errors: int = 0


@dataclass(frozen=True, slots=True)
class ReminderJobCandidate:
    job_id: int
    status: str
    claimed_at: datetime | None


async def process_due_reminder_jobs(
    sessionmaker: async_sessionmaker[AsyncSession],
    gateway: ReminderMessageGateway,
    *,
    now: datetime | None = None,
    limit: int = DEFAULT_BATCH_SIZE,
    reclaim_after: timedelta = DEFAULT_RECLAIM_AFTER,
    logger: logging.Logger | None = None,
) -> ReminderProcessingResult:
    run_at = (now or datetime.now()).replace(microsecond=0)
    candidates = await _list_candidates(
        sessionmaker,
        now=run_at,
        stale_before=run_at - reclaim_after,
        limit=limit,
    )

    result = ReminderProcessingResult(selected=len(candidates))
    for candidate in candidates:
        result = await _process_candidate(
            sessionmaker,
            gateway,
            candidate=candidate,
            now=run_at,
            result=result,
            logger=logger,
        )
    return result


async def _list_candidates(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    now: datetime,
    stale_before: datetime,
    limit: int,
) -> list[ReminderJobCandidate]:
    async with sessionmaker() as session:
        jobs = await repositories.list_due_reminder_jobs(
            session,
            now=now,
            stale_before=stale_before,
            limit=limit,
        )
        return [
            ReminderJobCandidate(job_id=job.id, status=job.status, claimed_at=job.claimed_at)
            for job in jobs
        ]


async def _process_candidate(
    sessionmaker: async_sessionmaker[AsyncSession],
    gateway: ReminderMessageGateway,
    *,
    candidate: ReminderJobCandidate,
    now: datetime,
    result: ReminderProcessingResult,
    logger: logging.Logger | None,
) -> ReminderProcessingResult:
    async with sessionmaker() as session:
        try:
            claimed = await repositories.claim_notification_job(
                session,
                job_id=candidate.job_id,
                expected_statuses=[candidate.status],
                expected_claimed_at=candidate.claimed_at,
                claimed_at=now,
            )
            if not claimed:
                await session.rollback()
                return _replace_result(result, claim_missed=result.claim_missed + 1)

            await session.commit()
            outcome = await ReminderDeliveryService(session, gateway).process_job(
                candidate.job_id,
                now=now,
            )
        except Exception:
            await session.rollback()
            if logger is not None:
                logger.exception("Failed to process reminder job %s", candidate.job_id)
            return _replace_result(result, errors=result.errors + 1)

    return _count_outcome(result, outcome)


def _count_outcome(
    result: ReminderProcessingResult,
    outcome: str,
) -> ReminderProcessingResult:
    if outcome == "sent":
        return _replace_result(result, claimed=result.claimed + 1, sent=result.sent + 1)
    if outcome == "skipped":
        return _replace_result(result, claimed=result.claimed + 1, skipped=result.skipped + 1)
    if outcome == "failed":
        return _replace_result(result, claimed=result.claimed + 1, failed=result.failed + 1)
    return _replace_result(result, claimed=result.claimed + 1, errors=result.errors + 1)


def _replace_result(
    result: ReminderProcessingResult,
    *,
    selected: int | None = None,
    claimed: int | None = None,
    claim_missed: int | None = None,
    sent: int | None = None,
    skipped: int | None = None,
    failed: int | None = None,
    errors: int | None = None,
) -> ReminderProcessingResult:
    return ReminderProcessingResult(
        selected=result.selected if selected is None else selected,
        claimed=result.claimed if claimed is None else claimed,
        claim_missed=result.claim_missed if claim_missed is None else claim_missed,
        sent=result.sent if sent is None else sent,
        skipped=result.skipped if skipped is None else skipped,
        failed=result.failed if failed is None else failed,
        errors=result.errors if errors is None else errors,
    )
