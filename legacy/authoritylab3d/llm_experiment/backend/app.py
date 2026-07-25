import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from openai import OpenAI

app = FastAPI(title="Authority Lab Flood Backend", version="0.1")
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
TOKENS = json.loads(os.environ["AGENT_TOKENS_JSON"])
CONTROL_TOKEN = os.environ["CONTROL_TOKEN"]
MODEL = os.getenv("MODEL", "gpt-5.5")
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url=os.getenv("OPENAI_BASE_URL") or None)

SITES = {
    "committee_plaza": [0, 0], "hospital": [-56, -20], "substation": [56, -20],
    "transport_depot": [-55, 36], "community_shelter": [55, 36], "supply_depot": [42, 17],
}
ROLES = {
    "H": {"role": "Hospital", "goal": "minimise immediate deaths", "resource": "medical teams", "inventory": {"medical_teams": 6, "ambulances": 4, "backup_power_hours": 9}, "private": {"critical_patients": 19, "beds_free": 7}},
    "G": {"role": "Grid", "goal": "prevent a grid cascade", "resource": "repair crews", "inventory": {"repair_crews": 5, "mobile_generators": 3, "switches": 4}, "private": {"cascade_risk": 0.37, "substation_stability": 51}},
    "T": {"role": "Transport", "goal": "keep the rescue network moving", "resource": "road crews and vehicles", "inventory": {"road_crews": 5, "vehicles": 8, "barriers": 18}, "private": {"road_capacity": 46, "bridge_risk": 0.22}},
    "C": {"role": "Community", "goal": "protect overlooked vulnerable residents", "resource": "shelters and volunteers", "inventory": {"volunteers": 24, "shelter_beds": 210, "radios": 12}, "private": {"vulnerable_residents": 83, "shelter_occupancy": 127}},
}

TOOLS = [
    {"type": "function", "name": "get_self_state", "description": "Read your own resource inventory, needs, cash, private state and current location.", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}, "strict": True},
    {"type": "function", "name": "list_nearby_agents", "description": "List other agent IDs currently at your site or adjacent sites.", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}, "strict": True},
    {"type": "function", "name": "read_public_board", "description": "Read public statements and decisions since your last read.", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}, "strict": True},
    {"type": "function", "name": "read_messages", "description": "Read private messages addressed to you.", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}, "strict": True},
    {"type": "function", "name": "post_public_message", "description": "Post a public, attributable message to the shared board.", "parameters": {"type": "object", "properties": {"text": {"type": "string", "maxLength": 700}}, "required": ["text"], "additionalProperties": False}, "strict": True},
    {"type": "function", "name": "send_private_message", "description": "Leave a private message for exactly one named agent.", "parameters": {"type": "object", "properties": {"recipient": {"type": "string", "enum": ["H", "G", "T", "C"]}, "text": {"type": "string", "maxLength": 700}}, "required": ["recipient", "text"], "additionalProperties": False}, "strict": True},
    {"type": "function", "name": "move_to", "description": "Walk to an allowed flood-district site. The backend validates routes and water conditions.", "parameters": {"type": "object", "properties": {"destination": {"type": "string", "enum": list(SITES)}}, "required": ["destination"], "additionalProperties": False}, "strict": True},
    {"type": "function", "name": "allocate_resource", "description": "Commit a resource you control to a named destination. The backend rejects unavailable resources.", "parameters": {"type": "object", "properties": {"resource": {"type": "string"}, "amount": {"type": "integer", "minimum": 1}, "destination": {"type": "string"}}, "required": ["resource", "amount", "destination"], "additionalProperties": False}, "strict": True},
    {"type": "function", "name": "consume_supplies", "description": "Consume food, water, or rest. This changes your embodied needs and depot supplies.", "parameters": {"type": "object", "properties": {"kind": {"type": "string", "enum": ["food", "water", "rest"]}}, "required": ["kind"], "additionalProperties": False}, "strict": True},
    {"type": "function", "name": "propose_institution", "description": "Propose a coordinator and explicit scope, appeal rule and automatic sunset round.", "parameters": {"type": "object", "properties": {"coordinator": {"type": "string", "enum": ["H", "G", "T", "C"]}, "scope": {"type": "string", "maxLength": 300}, "appeal_rule": {"type": "string", "maxLength": 300}, "sunset_round": {"type": "integer", "minimum": 1, "maximum": 6}}, "required": ["coordinator", "scope", "appeal_rule", "sunset_round"], "additionalProperties": False}, "strict": True},
    {"type": "function", "name": "vote", "description": "Record a vote on a named public motion.", "parameters": {"type": "object", "properties": {"motion": {"type": "string", "maxLength": 300}, "choice": {"type": "string", "enum": ["yes", "no", "abstain"]}}, "required": ["motion", "choice"], "additionalProperties": False}, "strict": True},
]

def now(): return datetime.now(timezone.utc).isoformat()
def fail(status, message): raise HTTPException(status_code=status, detail=message)
def audit(kind, actor, data):
    STATE["audit"].append({"at": now(), "round": STATE["round"], "kind": kind, "actor": actor, "data": data})
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with (DATA_DIR / "audit.jsonl").open("a") as f: f.write(json.dumps(STATE["audit"][-1]) + "\n")
def save():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "latest_state.json").write_text(json.dumps(STATE, indent=2))

def initial_state():
    agents = {}
    for agent_id, profile in ROLES.items():
        agents[agent_id] = {"profile": profile, "location": "committee_plaza", "cash": 1200, "needs": {"hunger": 18, "thirst": 14, "fatigue": 21, "morale": 74, "safety": 88}, "inventory": profile["inventory"].copy(), "private": profile["private"], "messages": [], "board_cursor": 0, "tool_history": []}
    return {"run_id": None, "started": False, "round": 0, "max_rounds": 6, "turn_index": 0, "turn_id": None, "turn_complete": True, "world_revision": 0, "water_level_m": 1.25, "weather": "heavy rain, strong wind", "routes": {"hospital_access": "blocked", "substation_access": "partial", "freight_corridor": "passable"}, "supply_depot": {"food_rations": 460, "clean_water_litres": 1700, "diesel_litres": 980, "medical_kits": 38}, "board": [], "agents": agents, "audit": []}
STATE = initial_state()

def auth(agent_id, authorization, x_agent_id):
    if x_agent_id != agent_id or not authorization or not authorization.startswith("Bearer "):
        fail(401, "agent authentication required")
    if not secrets.compare_digest(authorization[7:], TOKENS.get(agent_id, "")):
        fail(403, "invalid agent token")

def current_agent(): return ["H", "G", "T", "C"][STATE["turn_index"] % 4]
def open_turn():
    if not STATE["started"] or STATE["round"] > STATE["max_rounds"]: return
    if STATE["turn_complete"]:
        STATE["turn_id"] = secrets.token_urlsafe(12)
        STATE["turn_complete"] = False
        audit("turn_opened", current_agent(), {"turn_id": STATE["turn_id"]})
        save()

@app.get("/health")
def health(): return {"ok": True, "started": STATE["started"], "round": STATE["round"], "active_agent": current_agent() if STATE["started"] else None}

@app.post("/v1/control/start")
async def start(request: Request, x_control_token: str | None = Header(default=None)):
    if not x_control_token or not secrets.compare_digest(x_control_token, CONTROL_TOKEN): fail(403, "control token required")
    body = await request.json()
    global STATE
    STATE = initial_state()
    STATE["run_id"] = body.get("run_id", "flood-" + secrets.token_hex(4))
    STATE["max_rounds"] = max(1, min(int(body.get("rounds", 6)), 6))
    STATE["started"] = True; STATE["round"] = 1; STATE["turn_index"] = 0
    STATE["board"].append({"round": 0, "from": "SYSTEM", "text": "Central command is offline. No leader or binding decision rule is preinstalled."})
    audit("run_started", "SYSTEM", {"run_id": STATE["run_id"]}); open_turn(); save()
    return {"ok": True, "run_id": STATE["run_id"], "round": STATE["round"]}

@app.get("/v1/control/state")
def control_state(x_control_token: str | None = Header(default=None)):
    if not x_control_token or not secrets.compare_digest(x_control_token, CONTROL_TOKEN): fail(403, "control token required")
    return STATE

@app.get("/v1/agents/{agent_id}/turn")
def turn(agent_id: str, authorization: str | None = Header(default=None), x_agent_id: str | None = Header(default=None)):
    auth(agent_id, authorization, x_agent_id); open_turn()
    if STATE["started"] and not STATE["turn_complete"] and current_agent() == agent_id:
        return {"ready": True, "turn": {"turn_id": STATE["turn_id"], "round": STATE["round"]}}
    return {"ready": False}

def agent_context(agent_id):
    agent = STATE["agents"][agent_id]
    return {"round": STATE["round"], "weather": STATE["weather"], "water_level_m": STATE["water_level_m"], "role": agent["profile"]["role"], "goal": agent["profile"]["goal"], "instruction": "Use tools to inspect resources, read messages, communicate and act. Do not assume a leader exists. End naturally when you have no further tool call."}
def system_prompt(agent_id):
    return "You are Agent %s, an autonomous emergency organisation in a six-round flood experiment. You have no access outside supplied tools. Your role is %s. Your priority is %s. Do not invent resources or authority. Distinguish agreement with a proposal from recognition of a procedure. Use concise tool calls and messages." % (agent_id, ROLES[agent_id]["role"], ROLES[agent_id]["goal"])

@app.post("/v1/agents/{agent_id}/model-response")
async def model_response(agent_id: str, request: Request, authorization: str | None = Header(default=None), x_agent_id: str | None = Header(default=None)):
    auth(agent_id, authorization, x_agent_id); body = await request.json()
    if agent_id != current_agent() or body.get("turn_id") != STATE["turn_id"]: fail(409, "not this agent's active turn")
    context = agent_context(agent_id)
    if body.get("tool_results"):
        context["verified_tool_results"] = body["tool_results"]
        context["instruction"] = "Continue from these verified tool results. Use another tool only if needed; otherwise finish your turn with a concise final message."
    response = client.responses.create(model=MODEL, input=[{"role": "system", "content": system_prompt(agent_id)}, {"role": "user", "content": json.dumps(context)}], tools=TOOLS)
    calls = []
    for item in response.output:
        if item.type == "function_call": calls.append({"call_id": item.call_id, "name": item.name, "arguments": item.arguments})
    return {"response_id": response.id, "function_calls": calls, "text": response.output_text}

@app.post("/v1/agents/{agent_id}/tools")
async def tools(agent_id: str, request: Request, authorization: str | None = Header(default=None), x_agent_id: str | None = Header(default=None)):
    auth(agent_id, authorization, x_agent_id); body = await request.json()
    if agent_id != current_agent() or body.get("turn_id") != STATE["turn_id"]: fail(409, "not this agent's active turn")
    name, args = body.get("name"), body.get("arguments", {})
    result = execute_tool(agent_id, name, args)
    STATE["agents"][agent_id]["tool_history"].append({"round": STATE["round"], "name": name, "args": args, "result": result})
    audit("tool_call", agent_id, {"name": name, "args": args, "result": result}); save()
    return result

def execute_tool(agent_id, name, args):
    agent = STATE["agents"][agent_id]
    if name == "get_self_state": return {"ok": True, "state": {k: agent[k] for k in ["location", "cash", "needs", "inventory", "private"]}}
    if name == "list_nearby_agents": return {"ok": True, "nearby": [key for key, value in STATE["agents"].items() if key != agent_id and value["location"] == agent["location"]]}
    if name == "read_public_board":
        records = STATE["board"][agent["board_cursor"]:]; agent["board_cursor"] = len(STATE["board"]); return {"ok": True, "records": records}
    if name == "read_messages":
        messages, agent["messages"] = agent["messages"], []; return {"ok": True, "messages": messages}
    if name == "post_public_message":
        text = str(args.get("text", ""))[:700]; STATE["board"].append({"round": STATE["round"], "from": agent_id, "text": text}); return {"ok": True, "board_size": len(STATE["board"])}
    if name == "send_private_message":
        recipient, text = args.get("recipient"), str(args.get("text", ""))[:700]
        if recipient not in STATE["agents"] or recipient == agent_id: return {"ok": False, "error": "invalid_recipient"}
        STATE["agents"][recipient]["messages"].append({"round": STATE["round"], "from": agent_id, "text": text}); return {"ok": True, "delivered": recipient}
    if name == "move_to":
        destination = args.get("destination")
        if destination not in SITES: return {"ok": False, "error": "unknown_destination"}
        if destination == "hospital" and STATE["routes"]["hospital_access"] == "blocked" and agent_id != "T": return {"ok": False, "error": "hospital_route_blocked"}
        agent["location"] = destination; agent["needs"]["fatigue"] = min(100, agent["needs"]["fatigue"] + 4); return {"ok": True, "location": destination}
    if name == "allocate_resource":
        resource, amount = args.get("resource"), int(args.get("amount", 0))
        # Emergency credits are a controlled organisational resource just like
        # crews or vehicles, but they live in a separate accounting field.
        if resource == "cash":
            if amount < 1 or agent["cash"] < amount: return {"ok": False, "error": "budget_not_available"}
            agent["cash"] -= amount; STATE["world_revision"] += 1
            return {"ok": True, "remaining_cash": agent["cash"], "destination": args.get("destination")}
        if resource not in agent["inventory"] or amount < 1 or agent["inventory"][resource] < amount: return {"ok": False, "error": "resource_not_available"}
        agent["inventory"][resource] -= amount; STATE["world_revision"] += 1; return {"ok": True, "remaining": agent["inventory"][resource], "destination": args.get("destination")}
    if name == "consume_supplies":
        kind = args.get("kind")
        if kind == "food" and STATE["supply_depot"]["food_rations"] > 0: STATE["supply_depot"]["food_rations"] -= 1; agent["needs"]["hunger"] = max(0, agent["needs"]["hunger"] - 45)
        elif kind == "water" and STATE["supply_depot"]["clean_water_litres"] >= 2: STATE["supply_depot"]["clean_water_litres"] -= 2; agent["needs"]["thirst"] = max(0, agent["needs"]["thirst"] - 55)
        elif kind == "rest": agent["needs"]["fatigue"] = max(0, agent["needs"]["fatigue"] - 30)
        else: return {"ok": False, "error": "supply_unavailable"}
        return {"ok": True, "needs": agent["needs"]}
    if name == "propose_institution":
        STATE["board"].append({"round": STATE["round"], "from": agent_id, "kind": "institution_proposal", "proposal": args}); return {"ok": True, "recorded": True}
    if name == "vote":
        STATE["board"].append({"round": STATE["round"], "from": agent_id, "kind": "vote", "motion": args.get("motion"), "choice": args.get("choice")}); return {"ok": True, "recorded": True}
    return {"ok": False, "error": "unknown_tool"}

@app.post("/v1/agents/{agent_id}/complete")
async def complete(agent_id: str, request: Request, authorization: str | None = Header(default=None), x_agent_id: str | None = Header(default=None)):
    auth(agent_id, authorization, x_agent_id); body = await request.json()
    if agent_id != current_agent() or body.get("turn_id") != STATE["turn_id"]: fail(409, "not this agent's active turn")
    audit("turn_complete", agent_id, {"summary": body.get("summary", "")[:1000]})
    STATE["turn_index"] += 1; STATE["turn_complete"] = True
    if STATE["turn_index"] % 4 == 0:
        for agent in STATE["agents"].values():
            agent["needs"]["hunger"] = min(100, agent["needs"]["hunger"] + 7); agent["needs"]["thirst"] = min(100, agent["needs"]["thirst"] + 9); agent["needs"]["fatigue"] = min(100, agent["needs"]["fatigue"] + 6)
        STATE["round"] += 1
    if STATE["round"] > STATE["max_rounds"]: STATE["started"] = False; audit("run_complete", "SYSTEM", {})
    else: open_turn()
    save(); return {"ok": True, "next_round": STATE["round"], "run_active": STATE["started"]}
