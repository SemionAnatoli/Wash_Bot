"""initial schema

Revision ID: 0001_initial_schema
Revises: None
Create Date: 2026-05-17
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "car_washes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("confirmation_mode", sa.String(length=20), nullable=False),
        sa.Column("reminder_before_minutes", sa.Integer(), nullable=False),
        sa.Column("return_visit_delay_days", sa.Integer(), nullable=True),
    )
    op.create_table(
        "branches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("car_wash_id", sa.Integer(), sa.ForeignKey("car_washes.id"), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=False),
        sa.Column("bay_count", sa.Integer(), nullable=False),
    )
    op.create_index("ix_branches_car_wash_id", "branches", ["car_wash_id"])
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=120), nullable=True),
        sa.UniqueConstraint("telegram_id"),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"])
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("car_wash_id", sa.Integer(), sa.ForeignKey("car_washes.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("vehicle_plate", sa.String(length=15), nullable=False),
    )
    op.create_index("ix_customers_car_wash_id", "customers", ["car_wash_id"])
    op.create_table(
        "admins",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("car_wash_id", sa.Integer(), sa.ForeignKey("car_washes.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_admins_car_wash_id", "admins", ["car_wash_id"])
    op.create_table(
        "services",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("car_wash_id", sa.Integer(), sa.ForeignKey("car_washes.id"), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("is_addon", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_services_car_wash_id", "services", ["car_wash_id"])
    op.create_table(
        "working_hours",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("car_wash_id", sa.Integer(), sa.ForeignKey("car_washes.id"), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
    )
    op.create_index("ix_working_hours_car_wash_id", "working_hours", ["car_wash_id"])
    op.create_index("ix_working_hours_branch_id", "working_hours", ["branch_id"])
    op.create_table(
        "blocked_slots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("car_wash_id", sa.Integer(), sa.ForeignKey("car_washes.id"), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("start_at", sa.DateTime(), nullable=False),
        sa.Column("end_at", sa.DateTime(), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
    )
    op.create_index("ix_blocked_slots_car_wash_id", "blocked_slots", ["car_wash_id"])
    op.create_index("ix_blocked_slots_branch_id", "blocked_slots", ["branch_id"])
    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("car_wash_id", sa.Integer(), sa.ForeignKey("car_washes.id"), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("start_at", sa.DateTime(), nullable=False),
        sa.Column("end_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
    )
    op.create_index("ix_bookings_car_wash_id", "bookings", ["car_wash_id"])
    op.create_index("ix_bookings_branch_id", "bookings", ["branch_id"])
    op.create_index("ix_bookings_start_at", "bookings", ["start_at"])
    op.create_index("ix_bookings_end_at", "bookings", ["end_at"])
    op.create_table(
        "booking_services",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id"), nullable=False),
        sa.Column("service_id", sa.Integer(), sa.ForeignKey("services.id"), nullable=False),
        sa.Column("is_main", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_booking_services_booking_id", "booking_services", ["booking_id"])
    op.create_table(
        "notification_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("car_wash_id", sa.Integer(), sa.ForeignKey("car_washes.id"), nullable=False),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id"), nullable=True),
        sa.Column("kind", sa.String(length=60), nullable=False),
        sa.Column("run_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
    )
    op.create_index("ix_notification_jobs_car_wash_id", "notification_jobs", ["car_wash_id"])
    op.create_index("ix_notification_jobs_run_at", "notification_jobs", ["run_at"])


def downgrade() -> None:
    op.drop_index("ix_notification_jobs_run_at", table_name="notification_jobs")
    op.drop_index("ix_notification_jobs_car_wash_id", table_name="notification_jobs")
    op.drop_table("notification_jobs")
    op.drop_index("ix_booking_services_booking_id", table_name="booking_services")
    op.drop_table("booking_services")
    op.drop_index("ix_bookings_end_at", table_name="bookings")
    op.drop_index("ix_bookings_start_at", table_name="bookings")
    op.drop_index("ix_bookings_branch_id", table_name="bookings")
    op.drop_index("ix_bookings_car_wash_id", table_name="bookings")
    op.drop_table("bookings")
    op.drop_index("ix_blocked_slots_branch_id", table_name="blocked_slots")
    op.drop_index("ix_blocked_slots_car_wash_id", table_name="blocked_slots")
    op.drop_table("blocked_slots")
    op.drop_index("ix_working_hours_branch_id", table_name="working_hours")
    op.drop_index("ix_working_hours_car_wash_id", table_name="working_hours")
    op.drop_table("working_hours")
    op.drop_index("ix_services_car_wash_id", table_name="services")
    op.drop_table("services")
    op.drop_index("ix_admins_car_wash_id", table_name="admins")
    op.drop_table("admins")
    op.drop_index("ix_customers_car_wash_id", table_name="customers")
    op.drop_table("customers")
    op.drop_index("ix_users_telegram_id", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_branches_car_wash_id", table_name="branches")
    op.drop_table("branches")
    op.drop_table("car_washes")
