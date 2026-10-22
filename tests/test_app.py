"""Run: python -m pytest tests/  (no API key needed — the model is faked)."""
import json, os, sys
from types import SimpleNamespace as NS
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("REHABBER_PASSWORD", "Acorn")
os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ["FLASK_DEBUG"] = "1"

import app as hazel
import library


class FakeStream:
    def __init__(self, final, texts):
        self.final, self.text_stream = final, iter(texts)
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def get_final_message(self): return self.final

class FakeMessages:
    """First call: Hazel asks to search. Second call: she answers."""
    def __init__(self): self.calls = []
    def stream(self, **kw):
        self.calls.append(kw)
        if len(self.calls) == 1 and kw.get("tools"):
            tu = NS(type="tool_use", id="t1", name="search_bible", input={"query": "giardia"})
            return FakeStream(NS(stop_reason="tool_use", content=[tu]), [])
        return FakeStream(NS(stop_reason="end_turn", content=[NS(type="text", text="ok")]), ["Hi ", "there"])

def client():
    hazel.app.config["TESTING"] = True
    hazel._hits.clear()
    hazel.client = NS(messages=FakeMessages())
    return hazel.app.test_client()

def events(resp):
    return [json.loads(l[6:]) for l in resp.get_data(as_text=True).splitlines() if l.startswith("data: ")]

MSG = {"messages": [{"role": "user", "content": "help"}]}


def test_rehabber_chat_requires_login():
    c = client()
    assert c.post("/chat", json=MSG).status_code == 401
    # claiming rehabber mode from the browser does nothing
    assert c.post("/chat", json={**MSG, "mode": "rehabber"}).status_code == 401
    assert c.post("/chat", json={**MSG, "mode": "app"}).status_code == 401

def test_wrong_password_rejected():
    c = client()
    r = c.post("/rehabber", data={"password": "Scurry"})
    assert b"error" in r.data.lower() or r.status_code == 200
    assert c.post("/chat", json=MSG).status_code == 401

def test_login_then_chat_uses_library_tools():
    c = client()
    c.post("/rehabber", data={"password": "acorn "})       # case/space-insensitive like before
    r = c.post("/chat", json=MSG)
    assert r.status_code == 200
    ev = events(r)
    assert ev[-1] == {"done": True}
    assert "".join(e.get("text", "") for e in ev) == "Hi there"
    calls = hazel.client.messages.calls
    assert len(calls) == 2                                   # tool round trip happened
    names = {t["name"] for t in calls[0]["tools"]}
    assert names == {"search_bible", "read_sections"}       # no dose calculator on the website
    tool_result = calls[1]["messages"][-1]["content"][0]
    assert "Diarrhea" in tool_result["content"]

def test_goodsam_is_public_and_toolless():
    c = client()
    r = c.post("/chat", json={**MSG, "mode": "goodsam"})
    assert r.status_code == 200
    assert "tools" not in hazel.client.messages.calls[0]

def test_bad_history_rejected():
    c = client()
    for bad in [{"messages": "hi"}, {"messages": []},
                {"messages": [{"role": "system", "content": "x"}]},
                {"messages": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "yo"}]}]:
        assert c.post("/chat", json={**bad, "mode": "goodsam"}).status_code == 400

def test_rate_limit():
    c = client()
    for _ in range(hazel.RATE_LIMIT):
        assert c.post("/chat", json={**MSG, "mode": "goodsam"}).status_code == 200
    assert c.post("/chat", json={**MSG, "mode": "goodsam"}).status_code == 429

def test_errors_do_not_leak_details():
    c = client()
    def boom(**kw): raise RuntimeError("secret internal detail sk-ant-xyz")
    hazel.client = NS(messages=NS(stream=boom))
    ev = events(c.post("/chat", json={**MSG, "mode": "goodsam"}))
    assert "sk-ant" not in json.dumps(ev) and "error" in ev[-1]

def test_public_search_hides_clinical_sections():
    for hit in library.search("baytril enrofloxacin dose", "goodsam", 10):
        assert library.BY_ID[hit["id"]]["audience"] == "public"
    assert library.read_sections(["c0001"], "goodsam")

def test_dose_calculator_matches_bible_and_guards_input():
    r = library.calculate_dose("PANACUR (Fenbendazole)", "Giardia", 200)
    assert r["volume"] == "0.100 mL per dose"               # Bible table: 200 g -> 0.100 mL
    assert "warning" in library.calculate_dose("BAYTRIL (Enrofloxacin)", "Standard 10 mg/kg/day, once daily", 20)
    assert "error" in library.calculate_dose("PANACUR (Fenbendazole)", "Giardia", 0)
    assert "error" in library.calculate_dose("PANACUR (Fenbendazole)", "Giardia", 50000)
    assert "error" in library.calculate_dose("Not a drug", "x", 100)
