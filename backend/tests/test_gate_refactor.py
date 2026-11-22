"""The extracted read-only gate/impact functions must match the behavior of release()/impact()."""
from backend import db as m, workflow as w
from conftest import login, change, approved_revision, state

FACT = "adult.manufacturer_address"

def counts(db):
    return {c.__tablename__: len(m.rows(db, c)) for c in (m.Audit, m.Impact, m.Release, m.Approval, m.Validation, m.Revision)}

def test_release_blockers_equal_release_rejection_reasons(client):
    rev = approved_revision(client)
    change(client)  # newer approved fact makes the approved revision stale
    with m.transaction(False) as db:
        blockers = w.release_blockers(db, w.get(db, m.Revision, rev["id"]))
    assert any("newer approved version" in b for b in blockers)
    login(client, "releaser")
    r = client.post(f"/api/revisions/{rev['id']}/release")
    assert r.status_code == 409 and r.json()["reasons"] == blockers

def test_release_blockers_empty_when_release_succeeds(client):
    rev = approved_revision(client)
    with m.transaction(False) as db:
        assert w.release_blockers(db, w.get(db, m.Revision, rev["id"])) == []
    login(client, "releaser")
    assert client.post(f"/api/revisions/{rev['id']}/release").status_code == 200

def test_unapproved_revision_reports_blockers_without_writing(client):
    login(client, "author")
    label = next(l for l in state(client)["labels"] if l["key"] == "adult.box")
    with m.transaction(False) as db:
        rev = w.latest_revision(db, label["id"])
        before = counts(db)
        blockers = w.release_blockers(db, rev)
        assert "Approval of this exact artifact is required" in blockers
        assert counts(db) == before

def test_what_if_matches_persisted_impact_and_is_read_only(client):
    c = change(client)
    login(client, "author")
    persisted = client.post(f"/api/changes/{c['id']}/impact").json()["labels"]
    with m.transaction(False) as db:
        before = counts(db)
        hypo = w.what_if_impact(db, FACT)
        assert counts(db) == before
    strip = lambda items: [{**x, "paths": [p.split(" → ", 1)[1] for p in x["paths"]]} for x in items]
    assert strip(hypo["labels"]) == strip(persisted)
    assert {x["label_key"]: x["status"] for x in hypo["labels"]} == {
        "adult.box": "Affected", "adult.carton": "Affected", "pediatric.box": "Unaffected", "pediatric.carton": "Unaffected"}

def test_what_if_reports_approval_and_staleness_from_snapshot(client):
    rev = approved_revision(client)
    with m.transaction(False) as db:
        approval = m.latest(db, m.Approval, rev["id"])
        down = {d["label_key"]: d for d in w.what_if_impact(db, FACT)["downstream"]}
    assert down["adult.box"]["approval_id"] == approval.id and down["adult.box"]["would_become_stale"] is True
    assert down["adult.box"]["state"] == "Approved"
    assert down["pediatric.box"]["would_become_stale"] is False and down["pediatric.box"]["approval_id"] is None
