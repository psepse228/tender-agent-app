from types import SimpleNamespace

from app.jobs.refresh_all_tenants import _get_active_tenant_ids, run


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def select(self, *_a, **_k):
        return self

    def execute(self):
        return SimpleNamespace(data=self._rows)


class _FakeClient:
    def __init__(self, tenants, profiles=None):
        self._tenants = tenants
        self._profiles = profiles or []

    def table(self, name):
        if name == "tenants":
            return _FakeQuery(self._tenants)
        if name == "company_profile":
            return _FakeQuery(self._profiles)
        raise AssertionError(f"unexpected table {name}")


def _active_tenant(id_, email="rep@example.com"):
    return {"id": id_, "owner_email": email}


def _profile(tenant_id, text="Real company description"):
    return {"tenant_id": tenant_id, "profile_text": text}


def test_refreshes_every_tenant_with_a_real_email_and_profile(monkeypatch):
    fake_client = _FakeClient(
        tenants=[_active_tenant("t1"), _active_tenant("t2")],
        profiles=[_profile("t1"), _profile("t2")],
    )
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
    fake_client = _FakeClient(
        tenants=[_active_tenant("bad"), _active_tenant("good")],
        profiles=[_profile("bad"), _profile("good")],
    )
    monkeypatch.setattr(
        "app.jobs.refresh_all_tenants.get_supabase_client", lambda: fake_client
    )

    def fake_refresh(tenant_id, _client):
        if tenant_id == "bad":
            raise RuntimeError("boom")
        return {"tenders": [], "sources_status": []}

    monkeypatch.setattr("app.jobs.refresh_all_tenants.refresh_tenant", fake_refresh)

    run()  # must not raise


def test_skips_tenant_with_no_owner_email():
    """A manually-seeded test fixture (e.g. "Beta Test") isn't a real
    self-serve signup and should never burn real scoring cost."""
    client = _FakeClient(
        tenants=[_active_tenant("real", "rep@example.com"), _active_tenant("fixture", None)],
        profiles=[_profile("real"), _profile("fixture")],
    )

    active = _get_active_tenant_ids(client)

    assert active == ["real"]


def test_skips_tenant_with_no_profile_configured():
    """A real Google signup that never finished onboarding has nothing real
    to score scraped content against -- skip until they configure one."""
    client = _FakeClient(
        tenants=[_active_tenant("real"), _active_tenant("unfinished")],
        profiles=[_profile("real")],  # "unfinished" has no company_profile row at all
    )

    active = _get_active_tenant_ids(client)

    assert active == ["real"]


def test_skips_tenant_with_blank_profile_text():
    client = _FakeClient(
        tenants=[_active_tenant("real"), _active_tenant("blank")],
        profiles=[_profile("real"), _profile("blank", text="   ")],
    )

    active = _get_active_tenant_ids(client)

    assert active == ["real"]
