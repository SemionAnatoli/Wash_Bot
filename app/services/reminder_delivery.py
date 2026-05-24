from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import repositories
from app.services.reminder_messages import format_booking_reminder_text

DeliveryOutcome = Literal["sent", "skipped", "failed"]


class ReminderMessageGateway(Protocol):
    async def send_message(self, telegram_id: int, text: str) -> None: ...


@dataclass(frozen=True, slots=True)
class ReminderDeliveryService:
    db_session: AsyncSession
    gateway: ReminderMessageGateway

    async def process_job(self, job_id: int, *, now: datetime) -> DeliveryOutcome:
        row = await repositories.get_notification_job_with_booking_context(
            self.db_session,
            job_id=job_id,
        )
        if row is None:
            return "skipped"

        job, booking, customer, user = row
        if job.kind != "booking_reminder" or job.status != "processing" or job.claimed_at is None:
            return "skipped"

        attempts = job.attempts + 1

        if (
            booking is None
            or customer is None
            or user is None
            or booking.status != "confirmed"
            or booking.start_at <= now
        ):
            return await self._finalize_skipped(
                job_id=job.id,
                claimed_at=job.claimed_at,
                attempts=attempts,
            )

        try:
            await self.gateway.send_message(
                user.telegram_id,
                format_booking_reminder_text(booking.start_at),
            )
        except Exception:
            return await self._finalize_failed(
                job_id=job.id,
                claimed_at=job.claimed_at,
                attempts=attempts,
            )

        return await self._finalize_sent(
            job_id=job.id,
            claimed_at=job.claimed_at,
            attempts=attempts,
        )

    async def _finalize_sent(
        self,
        *,
        job_id: int,
        claimed_at: datetime,
        attempts: int,
    ) -> DeliveryOutcome:
        changed = await repositories.mark_notification_job_sent(
            self.db_session,
            job_id=job_id,
            claimed_at=claimed_at,
            attempts=attempts,
        )
        return await self._commit_terminal_state(changed=changed, outcome="sent")

    async def _finalize_skipped(
        self,
        *,
        job_id: int,
        claimed_at: datetime,
        attempts: int,
    ) -> DeliveryOutcome:
        changed = await repositories.mark_notification_job_skipped(
            self.db_session,
            job_id=job_id,
            claimed_at=claimed_at,
            attempts=attempts,
        )
        return await self._commit_terminal_state(changed=changed, outcome="skipped")

    async def _finalize_failed(
        self,
        *,
        job_id: int,
        claimed_at: datetime,
        attempts: int,
    ) -> DeliveryOutcome:
        changed = await repositories.mark_notification_job_failed(
            self.db_session,
            job_id=job_id,
            claimed_at=claimed_at,
            attempts=attempts,
        )
        return await self._commit_terminal_state(changed=changed, outcome="failed")

    async def _commit_terminal_state(
        self,
        *,
        changed: bool,
        outcome: DeliveryOutcome,
    ) -> DeliveryOutcome:
        if not changed:
            await self.db_session.rollback()
            raise RuntimeError("Notification job state changed concurrently.")
        await self.db_session.commit()
        return outcome
