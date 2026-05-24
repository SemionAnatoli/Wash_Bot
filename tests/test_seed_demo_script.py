from app.demo_seed import DemoSeedResult
from scripts import seed_demo


def test_format_seed_summary_includes_demo_ids() -> None:
    text = seed_demo.format_seed_summary(
        DemoSeedResult(
            car_wash_id=1,
            branch_id=1,
            main_service_count=2,
            addon_service_count=3,
            working_hours_count=7,
        )
    )

    assert "Demo data ready." in text
    assert "car_wash_id=1" in text
    assert "branch_id=1" in text
    assert "main_services=2" in text
    assert "addon_services=3" in text
    assert "working_hours=7" in text


async def test_run_seed_uses_settings_defaults(monkeypatch) -> None:
    calls: list[dict[str, int]] = []

    class FakeSettings:
        database_url = "sqlite+aiosqlite:///:memory:"
        default_car_wash_id = 10
        default_branch_id = 20

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

    def fake_sessionmaker():
        return FakeSession()

    def fake_create_sessionmaker(database_url: str):
        assert database_url == "sqlite+aiosqlite:///:memory:"
        return fake_sessionmaker

    async def fake_seed_demo_data(session, *, car_wash_id: int, branch_id: int):
        calls.append({"car_wash_id": car_wash_id, "branch_id": branch_id})
        return DemoSeedResult(car_wash_id, branch_id, 2, 3, 7)

    monkeypatch.setattr(seed_demo, "Settings", FakeSettings)
    monkeypatch.setattr(seed_demo, "create_sessionmaker", fake_create_sessionmaker)
    monkeypatch.setattr(seed_demo, "seed_demo_data", fake_seed_demo_data)

    result = await seed_demo.run_seed()

    assert result.car_wash_id == 10
    assert result.branch_id == 20
    assert calls == [{"car_wash_id": 10, "branch_id": 20}]
