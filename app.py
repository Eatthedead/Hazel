"""Hazel the Wonder Squirrel — web server.

Routes
  /            landing page
  /goodsam     Sam, for people who just found a baby (public)
  /rehabber    password gate -> Hazel for rehabbers
  /chat        streaming chat API (Server-Sent Events)

Environment variables (set in Railway -> Variables, never in code):
  ANTHROPIC_API_KEY   required
  SECRET_KEY          required — long random string; signs the login cookie
  REHABBER_PASSWORD   required — the website rehabber password
  HAZEL_MODEL         optional — defaults to the model Hazel has been running on
  RATE_LIMIT          optional — messages per IP per 10 minutes (default 30)
"""
import hmac, json, os, time
from collections import defaultdict, deque

import anthropic
from flask import Flask, Response, abort, render_template, request, session

import library
from prompts import GOOD_SAM_PROMPT, hazel_prompt

app = Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=os.environ.get("FLASK_DEBUG") != "1",
                  PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 30)

client = anthropic.Anthropic()                      # reads ANTHROPIC_API_KEY
MODEL = os.environ.get("HAZEL_MODEL", "claude-opus-4-5")
REHABBER_PASSWORD = os.environ["REHABBER_PASSWORD"]
RATE_LIMIT = int(os.environ.get("RATE_LIMIT", "30"))
MAX_TOOL_ROUNDS = 5


# ------------------------------------------------------------------ pages
@app.route("/")
def landing():
    return render_template("landing.html")

@app.route("/goodsam")
def goodsam():
    return render_template("goodsam.html")

@app.route("/rehabber", methods=["GET", "POST"])
def rehabber():
    if session.get("rehabber"):
        return render_template("index.html")
    if request.method == "POST":
        pw = request.form.get("password", "").strip().lower()
        if hmac.compare_digest(pw.encode(), REHABBER_PASSWORD.lower().encode()):
            session.permanent = True
            session["rehabber"] = True
            return render_template("index.html")
        time.sleep(1)                                   # slow down guessing
        return render_template("gate.html", error=True)
    return render_template("gate.html", error=False)


# ------------------------------------------------------------------ rate limit
_hits = defaultdict(deque)

def _client_ip():
    fwd = request.headers.get("X-Forwarded-For", "")
    return fwd.split(",")[0].strip() or request.remote_addr or "?"

def _rate_limited():
    now, q = time.time(), _hits[_client_ip()]
    while q and now - q[0] > 600:
        q.popleft()
    if len(q) >= RATE_LIMIT:
        return True
    q.append(now)
    return False


# ------------------------------------------------------------------ tools
TOOLS_LIBRARY = [
    dict(name="search_bible",
         description="Keyword search across every section of The Comprehensive Squirrel Bible. "
                     "Returns section ids, headings and a short preview.",
         input_schema=dict(type="object", properties=dict(
             query=dict(type="string", description="Specific terms: symptom, condition, drug, technique.")),
             required=["query"])),
    dict(name="read_sections",
         description="Read up to 4 Squirrel Bible sections in full by id (e.g. c0042).",
         input_schema=dict(type="object", properties=dict(
             ids=dict(type="array", items=dict(type="string"), maxItems=4)), required=["ids"])),
]
TOOLS_DOSING = [
    dict(name="list_regimens",
         description="List the formulary drugs/regimens the dose calculator knows, filtered by a drug name fragment.",
         input_schema=dict(type="object", properties=dict(drug=dict(type="string")), required=[])),
    dict(name="calculate_dose",
         description="Calculate an exact dose (mg and mL) from the Squirrel Bible formulary for a given weight. "
                     "Always use this; never do dose math yourself.",
         input_schema=dict(type="object", properties=dict(
             drug=dict(type="string"), regimen=dict(type="string"),
             weight_g=dict(type="number"),
             concentration_mg_per_mL=dict(type="number", description="Only if the product differs from the formulary's.")),
             required=["drug", "regimen", "weight_g"])),
]

def run_tool(name, args, mode):
    if name == "search_bible":
        return library.search(str(args.get("query", "")), mode)
    if name == "read_sections":
        return library.read_sections(list(args.get("ids", [])), mode)
    if mode == "app" and name == "list_regimens":
        return library.list_regimens(str(args.get("drug", "")))
    if mode == "app" and name == "calculate_dose":
        return library.calculate_dose(args.get("drug", ""), args.get("regimen", ""),
                                      args.get("weight_g"), args.get("concentration_mg_per_mL"))
    return dict(error=f"tool {name} is not available here")


# ------------------------------------------------------------------ chat
def _clean_history(raw):
    """Accept only plain user/assistant text turns, capped in size."""
    if not isinstance(raw, list):
        return None
    msgs = []
    for m in raw[-30:]:
        if not isinstance(m, dict) or m.get("role") not in ("user", "assistant"):
            return None
        c = m.get("content")
        if not isinstance(c, str) or not c.strip():
            return None
        msgs.append(dict(role=m["role"], content=c[:6000]))
    while msgs and msgs[0]["role"] != "user":
        msgs.pop(0)
    if not msgs or msgs[-1]["role"] != "user":
        return None
    return msgs

def _sse(obj):
    return "data: " + json.dumps(obj) + "\n\n"

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    messages = _clean_history(data.get("messages"))
    if messages is None:
        abort(400)

    # Mode comes from the server-side login, never from what the browser claims.
    if data.get("mode") == "goodsam":
        mode = "goodsam"
    elif session.get("rehabber"):
        mode = "rehabber"
    else:
        abort(401)
    if _rate_limited():
        return Response(_sse({"error": "Hazel needs a quick breather — please try again in a few minutes."}),
                        mimetype="text/event-stream", status=429)

    if mode == "goodsam":
        system, tools = GOOD_SAM_PROMPT, []
    else:
        system, tools = hazel_prompt(mode), TOOLS_LIBRARY + (TOOLS_DOSING if mode == "app" else [])

    def generate():
        convo = list(messages)
        try:
            for _ in range(MAX_TOOL_ROUNDS + 1):
                kwargs = dict(model=MODEL, max_tokens=2048, messages=convo,
                              system=[dict(type="text", text=system, cache_control=dict(type="ephemeral"))])
                if tools:
                    kwargs["tools"] = tools
                with client.messages.stream(**kwargs) as stream:
                    for text in stream.text_stream:
                        yield _sse({"text": text})
                    final = stream.get_final_message()
                if final.stop_reason != "tool_use":
                    break
                convo.append(dict(role="assistant", content=final.content))
                results = []
                for block in final.content:
                    if block.type == "tool_use":
                        out = run_tool(block.name, block.input or {}, mode)
                        results.append(dict(type="tool_result", tool_use_id=block.id,
                                            content=json.dumps(out, ensure_ascii=False)))
                convo.append(dict(role="user", content=results))
                if any(b.type == "text" and b.text.strip() for b in final.content):
                    yield _sse({"text": "\n\n"})
            yield _sse({"done": True})
        except Exception:
            app.logger.exception("chat failed")
            yield _sse({"error": "Hazel couldn't answer just now. Please try again."})

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.after_request
def security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    return resp


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
