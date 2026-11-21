import os
from pathlib import Path
from sqlalchemy import select, text
from . import db as m
from .auth import hash_password
from .storage import store, digest
from .workflow import upload, generate, validate, FIELDS

BASE = {
    "adult": {"product_name": "Synthetic Adult Tongue Depressor 150 mm", "manufacturer_name": "Synthetic Example Devices LLC",
              "manufacturer_address": "100 Research Way, Boston, MA 02110", "product_identifier": "SYN-TD-A150", "material": "Nonsterile birch wood",
              "box.pack_identifier": "SYN-A150-B100", "carton.pack_identifier": "SYN-A150-C1000", "box.quantity": "100 units", "carton.quantity": "1000 units"},
    "pediatric": {"product_name": "Synthetic Pediatric Tongue Depressor 140 mm", "manufacturer_name": "Synthetic Example Devices LLC",
              "manufacturer_address": "22 Demo Road, Austin, TX 78701", "product_identifier": "SYN-TD-P140", "material": "Nonsterile birch wood",
              "box.pack_identifier": "SYN-P140-B100", "carton.pack_identifier": "SYN-P140-C1000", "box.quantity": "100 units", "carton.quantity": "1000 units"},
}

DEMO_ROLE_NAMES = {
    "author": "Processor / Labeling Engineer",
    "reviewer": "Checker / Quality Reviewer",
    "releaser": "Releaser / Release Manager",
}

def refresh_demo_role_names(db):
    """Keep seeded demo identities aligned with the public workflow profiles."""
    renamed = []
    for role, name in DEMO_ROLE_NAMES.items():
        user = m.latest(db, m.User, role + "@labeltrace.demo")
        if user and user.data.get("name") != name:
            user.data = {**user.data, "name": name}
            renamed.append(role)
    if renamed:
        m.audit(db, "DEMO_ROLE_DISPLAY_NAMES_UPDATED", "demo-users", "system", {"roles": renamed})

def source_text(product, version=1, address=None):
    facts = dict(BASE[product])
    if address:
        facts["manufacturer_address"] = address
    return (f"SYNTHETIC DEMONSTRATION ONLY - NOT FOR MANUFACTURING\nProduct specification: {product} / Version {version}\n"
            + "\n".join(f"{k}: {v}" for k,v in facts.items()) + "\n").encode()

def seed(db, passwords=None):
    if m.rows(db, m.Product):
        # Update demo display names in place. Role keys, permissions, and
        # existing workflow history remain unchanged.
        refresh_demo_role_names(db)

        # The hosted sample is intentionally a public demonstration. Updating
        # passwords through the encrypted deployment environment keeps the UI
        # help text and existing seeded accounts in sync without resetting any
        # source, revision, approval, or release history.
        if os.getenv("SEED_DEMO", "1" if os.getenv("APP_ENV", "development") in {"development", "demo", "test"} else "0") == "1":
            roles = ("author", "reviewer", "releaser")
            if os.getenv("APP_ENV") == "production":
                configured = {r: os.getenv("LABELTRACE_" + r.upper() + "_PASSWORD", "") for r in roles}
            else:
                configured = {"author": "author-1234", "reviewer": "reviewer-1234", "releaser": "releaser-1234"}
            if any(len(value) < 10 for value in configured.values()) or len(set(configured.values())) != 3:
                raise RuntimeError("Hosted demo role passwords must be distinct and at least 10 characters")
            from .auth import verify_password
            rotated = []
            for role, password in configured.items():
                user = m.latest(db, m.User, role + "@labeltrace.demo")
                if user:
                    changes = {}
                    if not verify_password(password, user.data["password_hash"]):
                        changes["password_hash"] = hash_password(password)
                        rotated.append(role)
                    if changes:
                        user.data = {**user.data, **changes}
            if rotated:
                m.audit(db, "DEMO_ROLE_PASSWORDS_UPDATED", "demo-users", "system", {"roles": rotated})
        return
    users = {}
    if passwords is None:
        if os.getenv("APP_ENV","development") not in {"development","demo","test"}:
            passwords = {r: os.getenv("LABELTRACE_" + r.upper() + "_PASSWORD", "") for r in ("author","reviewer","releaser")}
            if any(len(value) < 10 for value in passwords.values()):
                raise RuntimeError("Cloud demo passwords must be at least 10 characters; default demo credentials are local only")
            if len(set(passwords.values())) != 3:
                raise RuntimeError("Cloud author, reviewer, and releaser passwords must be distinct")
        else:
            passwords = {"author": "author-1234", "reviewer": "reviewer-1234", "releaser": "releaser-1234"}
    for role, name in DEMO_ROLE_NAMES.items():
        users[role] = m.add(db, m.User, role + "@labeltrace.demo", {"name": name, "role": role,
            "password_hash": hash_password(passwords[role])})
    template = m.add(db, m.Template, "tongue-depressor-US", {"name": "US-English controlled label", "field_width": 405,
        "required_fields": ["product_name", "manufacturer_name", "manufacturer_address", "product_identifier", "pack_identifier", "quantity", "material"],
        "page_points": [540, 360], "market": "US", "language": "en", "synthetic": True})
    m.add(db, m.RuleSet, "US-EN", {"name": "Selected US label checks + internal integrity checks", "sources": [
        {"rule": "US-801.1-SUBSET", "url": "https://www.ecfr.gov/current/title-21/section-801.1", "accessed": "2026-10-22",
         "scope": "Presence of approved manufacturer name and address only; not a complete 801.1 assessment"},
        {"rule": "LAYOUT-BOUNDS", "url": "https://www.ecfr.gov/current/title-21/section-801.15", "accessed": "2026-10-22",
         "scope": "Engineering check inspired by prominence; fixed template bounds are prototype assumptions, not regulatory dimensional thresholds"}],
        "notice": "Internal checks do not establish regulatory compliance. Internal QR is not UDI."})
    for product, facts in BASE.items():
        m.add(db, m.Product, product, {"name": facts["product_name"], "family": "Synthetic nonsterile tongue depressors", "market": "US", "language": "en", "synthetic": True})
        source = upload(db, product, f"SYNTHETIC-{product}-spec-v1.txt", source_text(product), users["author"])
        candidates = [c for c in m.rows(db, m.Candidate) if c.data["source_id"] == source.id]
        for c in candidates:
            m.add(db, m.Decision, "candidate:" + c.id, {"subject_type": "candidate", "subject_id": c.id, "decision": "Approved", "reason": "Synthetic seed baseline"}, users["reviewer"].id)
            m.add(db, m.Fact, c.data["fact_key"], {"value": c.data["value"], "source_id": source.id,
                "candidate_id": c.id, "evidence": {k:c.data[k] for k in ("page", "start", "end", "quote")}}, users["reviewer"].id)
        for level in ("box", "carton"):
            m.add(db, m.Packaging, product + "." + level, {"product": product, "level": level,
                "quantity": facts[level+".quantity"], "identifier": facts[level+".pack_identifier"]})
            label = m.add(db, m.Label, product + "." + level, {"product": product, "level": level,
                "market": "US", "language": "en", "template_key": template.key})
            for field in template.data["required_fields"]:
                fact_field = level+"."+field if field in {"pack_identifier", "quantity"} else field
                db.add(m.Dependency(label_id=label.id, field=field, fact_key=product+"."+fact_field, condition={"product": product, "level": level, "market": "US", "language": "en"}))
            db.flush()
            rev = generate(db, label, None, users["author"])
            validate(db, rev, users["author"])
    m.audit(db, "DEMO_INITIALIZED", "tongue-depressor-family", "system")

def write_fixtures():
    fixtures = m.ROOT / "fixtures"
    fixtures.mkdir(exist_ok=True)
    (fixtures / "SYNTHETIC-adult-spec-v2.txt").write_bytes(source_text("adult", 2, "200 Research Way, Boston, MA 02110"))
    (fixtures / "SYNTHETIC-adult-spec-v3.txt").write_bytes(source_text("adult", 3, "300 Research Way, Boston, MA 02110"))
    from reportlab.pdfgen.canvas import Canvas
    for v in (2, 3):
        c = Canvas(str(fixtures / f"SYNTHETIC-adult-spec-v{v}.pdf"))
        for i,line in enumerate((fixtures / f"SYNTHETIC-adult-spec-v{v}.txt").read_text().splitlines()):
            c.drawString(32, 800-i*23, line)
        c.save()

def initialize(reset=False):
    if reset:
        if os.getenv("APP_ENV", "development") not in {"development", "demo", "test"}:
            raise RuntimeError("Reset is restricted to development/demo/test environments")
        m.Base.metadata.drop_all(m.engine)
    if m.engine.dialect.name == "postgresql":
        # Vercel may start several Python instances at once. Serialize the
        # first DDL pass with a transaction-scoped advisory lock so concurrent
        # create_all(checkfirst=True) calls cannot race on PostgreSQL catalogs.
        with m.engine.begin() as connection:
            connection.execute(text("SELECT pg_advisory_xact_lock(715332541)"))
            m.Base.metadata.create_all(connection)
            connection.execute(text("INSERT INTO workflow_gate (id) VALUES (1) ON CONFLICT (id) DO NOTHING"))
    else:
        m.Base.metadata.create_all(m.engine)
        with m.Session.begin() as db:
            if not db.get(m.Gate, 1):
                db.add(m.Gate(id=1))
    with m.transaction() as db:
        # Apply the profile labels even when production demo seeding is disabled.
        # This updates display metadata only; it never resets workflow history.
        refresh_demo_role_names(db)
        if os.getenv("SEED_DEMO", "1" if os.getenv("APP_ENV","development") in {"development","demo","test"} else "0") == "1":
            seed(db)
    if os.getenv("APP_ENV","development") in {"development","demo","test"}:
        write_fixtures()

if __name__ == "__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    args=parser.parse_args()
    initialize(args.reset)
    print("Synthetic demo initialized. Author/reviewer/releaser accounts: *@labeltrace.demo")
