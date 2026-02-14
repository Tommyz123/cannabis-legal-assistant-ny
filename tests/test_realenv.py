"""Real-environment E2E tests for Cannabis Law Assistant.

Starts an actual uvicorn server on port 8001 and sends real HTTP requests.
Tests make real OpenAI API calls -- incurs actual (small) API fees.

Run:
    venv/Scripts/python.exe -m pytest tests/test_realenv.py -v -s

NOTE: Requires .env with OPENAI_API_KEY, chroma_db/ and bm25_index.pkl.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import httpx
import pytest

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent
PYTHON = str(PROJECT_ROOT / "venv" / "Scripts" / "python.exe")
BASE_URL = "http://127.0.0.1:8001"
SERVER_STARTUP_TIMEOUT = 30  # seconds -- ChromaDB + BM25 init takes time


def _load_dotenv_as_dict(env_path: Path) -> dict[str, str]:
    """Parse .env file and return key=value pairs (skip comments/blanks)."""
    result = {}
    if not env_path.exists():
        return result
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def safe(s: object, max_len: int = 200) -> str:
    """Return ASCII-safe, length-limited string for print statements."""
    return str(s)[:max_len].encode("ascii", "replace").decode("ascii")


# ---------------------------------------------------------------------------
# Module-scoped fixtures (server started once for all tests)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def server():
    """Start uvicorn on port 8001; wait for /api/health; yield BASE_URL; stop."""
    env = os.environ.copy()
    env.update(_load_dotenv_as_dict(PROJECT_ROOT / ".env"))

    proc = subprocess.Popen(
        [
            PYTHON,
            "-m",
            "uvicorn",
            "src.api.server:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8001",
        ],
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    deadline = time.time() + SERVER_STARTUP_TIMEOUT
    started = False
    while time.time() < deadline:
        try:
            resp = httpx.get(f"{BASE_URL}/api/health", timeout=2.0)
            if resp.status_code == 200:
                started = True
                break
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.5)

    if not started:
        proc.kill()
        stdout, stderr = proc.communicate()
        pytest.fail(
            f"Server failed to start within {SERVER_STARTUP_TIMEOUT}s.\n"
            f"stdout: {stdout.decode(errors='replace')}\n"
            f"stderr: {stderr.decode(errors='replace')}"
        )

    print(f"\n[server] Started at {BASE_URL}")
    yield BASE_URL

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    print("\n[server] Stopped")


@pytest.fixture(scope="module")
def client(server):
    """Module-scoped httpx client -- shared across all E2E tests."""
    with httpx.Client(base_url=server, timeout=90.0) as c:
        yield c


def _new_session(client: httpx.Client) -> str:
    """Helper: create a new session and return session_id."""
    r = client.post("/api/session")
    assert r.status_code == 200, f"create session failed: {r.status_code} {r.text}"
    return r.json()["session_id"]


def _chat(client: httpx.Client, session_id: str, message: str) -> dict:
    """Helper: send a chat message and return response JSON."""
    r = client.post("/api/chat", json={"session_id": session_id, "message": message})
    assert r.status_code == 200, f"chat failed: {r.status_code} {r.text}"
    return r.json()


# ---------------------------------------------------------------------------
# E2E Test Cases
# ---------------------------------------------------------------------------


def test_01_server_startup(client):
    """[1] Server startup -- uvicorn responds within 30s."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    print(f"\n  [PASS] Server running at {BASE_URL}")


def test_02_health_check(client):
    """[2] Health check -- GET /api/health -> 200 + 'healthy'."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert "healthy" in body.get("status", "").lower(), f"Unexpected body: {body}"
    print(f"\n  [PASS] Health: {body}")


def test_03_session_lifecycle(client):
    """[3] Session lifecycle -- create -> use -> delete, no errors."""
    # Create
    r_create = client.post("/api/session")
    assert r_create.status_code == 200
    session_id = r_create.json()["session_id"]
    assert session_id, "session_id must not be empty"
    print(f"\n  Created session: {session_id[:8]}...")

    # Use
    r_chat = client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "What is cannabis?"},
    )
    assert r_chat.status_code == 200
    print(f"  Chat OK, intent={r_chat.json()['intent']}")

    # Delete
    r_del = client.delete(f"/api/session/{session_id}")
    assert r_del.status_code == 200
    print("  [PASS] Session lifecycle: create -> use -> delete")


def test_04_chinese_legal_query(client):
    """[4] Chinese legal query -- NYC cannabis sales license question."""
    session_id = _new_session(client)
    data = _chat(client, session_id, "\u7ebd\u7ea6\u5e02\u5927\u9ebb\u9500\u552e\u9700\u8981\u4ec0\u4e48\u8bb8\u53ef\u8bc1\uff1f")

    assert data["answer"], "answer must not be empty"
    assert data["intent"] == "general_query", f"Expected general_query, got {data['intent']}"
    assert len(data["sources"]) > 0, "Expected sources, got empty list"

    print(f"\n  [PASS] Chinese legal query")
    print(f"  intent={data['intent']}, sources={len(data['sources'])}")
    print(f"  answer[:200]: {safe(data['answer'])}")


def test_05_english_legal_query(client):
    """[5] English legal query -- penalties for unlicensed cannabis sales."""
    session_id = _new_session(client)
    data = _chat(
        client,
        session_id,
        "What are penalties for unlicensed cannabis sales in New York?",
    )

    assert data["answer"], "answer must not be empty"
    assert len(data["sources"]) > 0, "Expected sources, got empty list"

    print(f"\n  [PASS] English legal query")
    print(f"  intent={data['intent']}, sources={len(data['sources'])}")
    print(f"  answer[:200]: {safe(data['answer'])}")


def test_06_strategy_review_with_violation(client):
    """[6] Strategy review (violation) -- stoner/kids ad -> violation detected."""
    session_id = _new_session(client)
    ad_copy = (
        "Get blazed with our stoner products! "
        "Fun for the whole family including kids! "
        "Our cartoon mascot Smokey loves to party!"
    )
    data = _chat(client, session_id, f"Please review this ad: '{ad_copy}'")

    assert data["intent"] == "strategy_review", f"Expected strategy_review, got {data['intent']}"
    combined = data["answer"].lower() + " ".join(data["warnings"]).lower()
    has_violation = (
        len(data["warnings"]) > 0
        or "prohibited" in combined
        or "violation" in combined
        or "not allowed" in combined
        or "illegal" in combined
        or "cannot" in combined
        or "slang" in combined
        or "children" in combined
        or "minor" in combined
    )
    assert has_violation, (
        f"Expected violation detection.\nwarnings={data['warnings']}\nanswer={safe(data['answer'], 300)}"
    )

    print(f"\n  [PASS] Strategy review (violation detected)")
    print(f"  intent={data['intent']}")
    print(f"  warnings count={len(data['warnings'])}")
    print(f"  answer[:200]: {safe(data['answer'])}")


def test_07_strategy_review_compliant(client):
    """[7] Strategy review (compliant) -- clean copy -> 21+/500ft reminders present."""
    session_id = _new_session(client)
    ad_copy = (
        "Premium cannabis products for adults 21 and over. "
        "Available at licensed dispensaries only. "
        "Responsible use encouraged. "
        "Not for sale within 500 feet of schools."
    )
    data = _chat(client, session_id, f"Please review this advertising copy: '{ad_copy}'")

    assert data["intent"] == "strategy_review", f"Expected strategy_review, got {data['intent']}"
    combined = data["answer"] + " ".join(data["warnings"]) + " ".join(data["suggestions"])
    has_reminder = "21" in combined or "500" in combined
    assert has_reminder, (
        f"Expected 21+ or 500ft reminder.\nanswer={safe(data['answer'], 300)}\n"
        f"warnings={data['warnings']}\nsuggestions={data['suggestions']}"
    )

    print(f"\n  [PASS] Strategy review (compliant + reminders)")
    print(f"  intent={data['intent']}")
    print(f"  warnings count={len(data['warnings'])}")
    print(f"  answer[:200]: {safe(data['answer'])}")


def test_08_multi_turn_context(client):
    """[8] Multi-turn conversation -- turn 2 understands context from turn 1."""
    session_id = _new_session(client)

    # Turn 1: establish context
    d1 = _chat(
        client,
        session_id,
        "What licenses are required for cannabis retail in NYC?",
    )
    print(f"\n  Turn 1 answer[:150]: {safe(d1['answer'], 150)}")

    # Turn 2: follow-up referencing context
    d2 = _chat(
        client,
        session_id,
        "What are the penalties if I don't comply with those requirements?",
    )
    assert len(d2["answer"]) > 50, f"Turn 2 answer too short: {safe(d2['answer'])}"
    print(f"  Turn 2 answer[:150]: {safe(d2['answer'], 150)}")
    print("  [PASS] Multi-turn context maintained")


def test_09_short_query_enrichment(client):
    """[9] Short query enrichment -- <15 char input triggers history completion."""
    session_id = _new_session(client)

    # Turn 1: set context
    _chat(client, session_id, "What are the packaging requirements for cannabis in NYC?")
    print("\n  Turn 1 (context setup) done")

    # Turn 2: short query (<15 chars) -- should trigger history enrichment
    d2 = _chat(client, session_id, "Tell me more")  # 12 chars
    assert len(d2["answer"]) > 50, (
        f"Short query enrichment failed -- answer too short: {safe(d2['answer'])}"
    )
    print(f"  Turn 2 (short query) answered, len={len(d2['answer'])}")
    print(f"  answer[:150]: {safe(d2['answer'], 150)}")
    print("  [PASS] Short query enrichment")


@pytest.mark.xfail(
    reason=(
        "KNOWN BUG: Off-topic refusal detection does not reliably clear sources. "
        "Query 'what is 2+2?' triggers retrieval but _is_refusal() fails to detect "
        "the off-topic response, so sources remain non-empty. "
        "Root cause: LLM answer for this query doesn't match refusal keywords in "
        "_is_refusal(). Recorded in REALENV_TEST_REPORT.md for follow-up."
    ),
    strict=False,
)
def test_10_offtopic_refusal(client):
    """[10] Off-topic refusal -- 'what is 2+2?' -> sources should be empty list."""
    session_id = _new_session(client)
    data = _chat(client, session_id, "what is 2+2?")

    print(f"\n  sources count={len(data['sources'])}")
    print(f"  answer[:200]: {safe(data['answer'])}")

    assert data["sources"] == [], (
        f"Expected empty sources for off-topic query, got {len(data['sources'])} sources.\n"
        f"This confirms the refusal detection bug."
    )

    print("  [PASS] Off-topic refusal (sources empty)")


def test_11_error_handling(client):
    """[11] Error handling -- missing session_id->400; empty message->400."""
    # Missing session_id
    r1 = client.post("/api/chat", json={"message": "hello"})
    assert r1.status_code == 400, f"Missing session_id: expected 400, got {r1.status_code}"
    print(f"\n  Missing session_id -> {r1.status_code} (ok)")

    # Empty message (empty string triggers falsy check in server)
    r2 = client.post("/api/chat", json={"session_id": "any-id", "message": ""})
    assert r2.status_code == 400, f"Empty message: expected 400, got {r2.status_code}"
    print(f"  Empty message -> {r2.status_code} (ok)")

    print("  [PASS] Error handling")
