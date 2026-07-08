from types import SimpleNamespace

from app.jobs.refresh_all_tenants import run


class _FakeTenantsQuery:
    def __init__(self, rows):
        self._rows = rows

    def select(self, *_a, **_k):
        return self

    def execute(self):
        return SimpleNamespace(data=self._rows)


class _FakeClient:
    def __init__(self, rows):
        self._rows = rows

    def table(self, name):
        assert name == "tenants"
        return _FakeTenantsQuery(self._rows)


def test_refreshes_every_tenant(monkeypatch):
    fake_client = _FakeClient([{"id": "t1"}, {"id": "t2"}])
    monkeypatch.setattr(
        "app.jobs.refresh_all_tenants.get_supabase_client", lambda: fake_client
    )
    calls = []
    monkeypatch.setattr(
        "app.jobs.refresh_all_tenants.refresh_tenant",
        lambda tenant_id, client: calls.append(tenant_id),
    )

    run()

    assert calls == ["t1", "t2"]


def test_continues_past_a_failing_tenant(monkeypatch):
    fake_client = _FakeClient([{"id": "bad"}, {"id": "good"}])
    monkeypatch.setattr(
        "app.jobs.refresh_all_tenants.get_supabase_client", lambda: fake_client
    )

    def fake_refresh(tenant_id, _client):
        if tenant_id == "bad":
            raise RuntimeError("boom")
        return {"tenders": [], "sources_status": []}

    monkeypatch.setattr("app.jobs.refresh_all_tenants.refresh_tenant", fake_refresh)

    run()  # must not raise
