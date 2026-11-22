"""vercel.json guards: existing routing/exclusions are preserved and the AI agent cannot outlive the function."""
import json
import subprocess
from pathlib import Path

from backend.agent import orchestrator as ag

ROOT = Path(__file__).resolve().parents[2]
CONFIG = json.loads((ROOT / "vercel.json").read_text())
API = CONFIG["services"]["api"]
FUNCTION = API["functions"]["backend/main.py"]
MAX_DURATION_CEILING = 60  # documented Hobby limit without Fluid compute; Hobby with Fluid allows 300

def test_function_key_is_the_real_resolved_entrypoint():
    module, _, attr = API["entrypoint"].partition(":")
    assert (ROOT / (module.replace(".", "/") + ".py")).is_file() and "backend/main.py" in API["functions"]

def test_max_duration_is_set_and_within_documented_limits():
    assert isinstance(FUNCTION["maxDuration"], int) and 1 <= FUNCTION["maxDuration"] <= MAX_DURATION_CEILING

def test_agent_deadline_fits_inside_function_duration(monkeypatch):
    monkeypatch.delenv("AGENT_TIMEOUT_SECONDS", raising=False)
    # leave headroom for persistence and response serialization after the model loop ends
    assert ag.settings()["timeout"] + 10 <= FUNCTION["maxDuration"]

def test_existing_configuration_is_preserved():
    original = json.loads(subprocess.run(["git", "show", "79e1ea0:vercel.json"], cwd=ROOT, capture_output=True, text=True, check=True).stdout)
    current = json.loads(json.dumps(CONFIG))
    del current["services"]["api"]["functions"]["backend/main.py"]["maxDuration"]
    assert current == original

def test_agent_is_disabled_by_default(monkeypatch):
    for name in ("AGENT_ENABLED", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    assert ag.agent_configured() is False
    monkeypatch.setenv("ANTHROPIC_API_KEY", "placeholder")   # a key alone must not enable the agent
    assert ag.agent_configured() is False
    monkeypatch.setenv("AGENT_ENABLED", "1")
    assert ag.agent_configured() is True
    assert "AGENT_ENABLED=0" in (ROOT / ".env.example").read_text()
    assert "maxDuration" not in json.dumps({k: v for k, v in API.items() if k != "functions"})
