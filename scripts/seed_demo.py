import asyncio

from app.config import Settings
from app.db.session import create_sessionmaker
from app.demo_seed import DemoSeedResult, seed_demo_data


def format_seed_summary(result: DemoSeedResult) -> str:
    return (
        "Demo data ready.\n"
        f"car_wash_id={result.car_wash_id}\n"
        f"branch_id={result.branch_id}\n"
        f"main_services={result.main_service_count}\n"
        f"addon_services={result.addon_service_count}\n"
        f"working_hours={result.working_hours_count}"
    )


async def run_seed() -> DemoSeedResult:
    settings = Settings()
    sessionmaker = create_sessionmaker(str(settings.database_url))
    async with sessionmaker() as session:
        return await seed_demo_data(
            session,
            car_wash_id=settings.default_car_wash_id,
            branch_id=settings.default_branch_id,
        )


async def async_main() -> None:
    result = await run_seed()
    print(format_seed_summary(result))


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
