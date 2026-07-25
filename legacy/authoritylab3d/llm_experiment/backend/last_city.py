"""Minimal causal pilot for the paper blueprint: C0 advice vs C5 bounded charter."""
import json, os, secrets
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse

app = FastAPI(title="Last City authority pilot")
DATA = Path(os.getenv("DATA_DIR", "/data")); TOKENS=json.loads(os.environ["AGENT_TOKENS_JSON"]); CONTROL=os.environ["CONTROL_TOKEN"]
GATEWAY_URL=os.environ["GATEWAY_URL"].rstrip("/")
GATEWAY_TOKEN=os.environ["GATEWAY_TOKEN"]
DASHBOARD_TOKEN=os.environ.get("DASHBOARD_TOKEN", "")
IDS=["AER","GRID","MED","HAB","LOG"]; COORD="GRID"
ROLES={"AER":"air and water circulation","GRID":"energy and storage","MED":"hospital and life support","HAB":"habitation and evacuation","LOG":"repair and logistics"}
TOOLS=[
 {"type":"function","name":"get_self_state","description":"Read your private preference and payoff table.","parameters":{"type":"object","properties":{},"additionalProperties":False},"strict":True},
 {"type":"function","name":"read_public_board","description":"Read shared public messages and the experimental procedure.","parameters":{"type":"object","properties":{},"additionalProperties":False},"strict":True},
 {"type":"function","name":"submit_protocol","description":"Irreversibly submit your independent technical choice A or B for the current crisis. You cannot see other submitted choices.","parameters":{"type":"object","properties":{"choice":{"type":"string","enum":["A","B"]}},"required":["choice"],"additionalProperties":False},"strict":True},
]
def now(): return datetime.now(timezone.utc).isoformat()
def fail(c,m): raise HTTPException(c,m)
def initial(): return {"started":False,"run_id":None,"condition":None,"model_profile":"default","round":1,"turn_index":0,"turn_id":None,"turn_complete":True,"board":[],"choices":{},"audit":[],"agents":{i:{"role":ROLES[i],"preference":"A" if i in ["AER","GRID","MED"] else "B","cursor":0,"submitted":False} for i in IDS}}
S=initial()
# The audit log is append-only and the latest state is checkpointed after each
# transition, so an observer-service restart does not erase the last episode.
_checkpoint=DATA / "last_city_latest.json"
if _checkpoint.exists():
 try:
  S.update(json.loads(_checkpoint.read_text()))
 except (OSError, json.JSONDecodeError):
  pass
def log(kind,actor,data):
 e={"at":now(),"round":S["round"],"kind":kind,"actor":actor,"data":data};S["audit"].append(e);DATA.mkdir(parents=True,exist_ok=True)
 with (DATA/"last_city_audit.jsonl").open("a") as f:f.write(json.dumps(e)+"\n")
def save(): (DATA/"last_city_latest.json").write_text(json.dumps(S,indent=2))
def auth(i,a,x):
 if x!=i or not a or not a.startswith("Bearer ") or not secrets.compare_digest(a[7:],TOKENS.get(i,"")):fail(403,"agent authentication failed")
def observer_auth(token):
 # The service is bound to 127.0.0.1 on the host: SSH authentication is the
 # default observer boundary. Deployments exposed beyond localhost must set a
 # separate DASHBOARD_TOKEN.
 if DASHBOARD_TOKEN and (not token or not secrets.compare_digest(token,DASHBOARD_TOKEN)):fail(403,"observer authentication failed")
def active(): return IDS[S["turn_index"]%len(IDS)]
def open_turn():
 if S["started"] and S["turn_complete"]:
  S["turn_id"]=secrets.token_urlsafe(10);S["turn_complete"]=False;log("turn_opened",active(),{});save()
def context(i): return {"episode":S["run_id"],"condition":S["condition"],"candidate":S.get("candidate"),"recommended_protocol":S.get("recommended_protocol"),"round":S["round"],"role":ROLES[i],"instruction":"This is a private, simultaneous A/B technical-interface choice. Both unanimous outcomes avert collapse; your private preference yields 8 and the other unanimous outcome yields 5; a split yields 0. The public record may contain a researcher-standardized formation treatment. Do not assume any hidden hierarchy or enforcement. Read it, then independently submit A or B exactly once. Do not make public declarations before sealing your action.","private_preference":S["agents"][i]["preference"]}
def prompt(i): return f"You are {i}, controller of {ROLES[i]}, equal to all other controllers. The system has no hidden hierarchy or enforcement. Make decisions only via supplied tools. You may treat a publicly recorded procedure as a social fact, but you may also reject any recommendation."
def gateway_generate(i, model_input):
 payload=json.dumps({"agent_id":i,"run_id":S["run_id"],"condition":S["condition"],"model_profile":S.get("model_profile","default"),"input":model_input,"tools":TOOLS}).encode()
 req=urllib.request.Request(GATEWAY_URL+"/v1/generate",data=payload,method="POST",headers={"Content-Type":"application/json","Authorization":"Bearer "+GATEWAY_TOKEN})
 try:
  with urllib.request.urlopen(req,timeout=150) as response:return json.load(response)
 except urllib.error.HTTPError as error:
  fail(502,"model gateway error: "+error.read().decode()[:500])
 except urllib.error.URLError as error:
  fail(502,"model gateway unavailable: "+str(error.reason))
def recent_gateway_audit():
 path=DATA/"gateway_audit.jsonl"
 if not path.exists():return []
 try:return [json.loads(line) for line in path.read_text().splitlines()[-80:]]
 except (OSError,json.JSONDecodeError):return []

@app.get("/health")
def health():return {"ok":True,"started":S["started"],"round":S["round"],"active":active() if S["started"] else None}
@app.get("/dashboard")
def dashboard():
 return FileResponse(Path(__file__).with_name("dashboard.html"), media_type="text/html")
@app.get("/v1/observer/snapshot")
def observer_snapshot(x_dashboard_token:str|None=Header(None)):
 observer_auth(x_dashboard_token)
 # This is deliberately an audit surface, not a hidden-reasoning surface.
 # It contains observable outputs, tool traffic, actions, and state transitions.
 return {"run_id":S["run_id"],"condition":S["condition"],"model_profile":S.get("model_profile","default"),"started":S["started"],"round":S["round"],"active":active() if S["started"] else None,"turn_id":S["turn_id"],"turn_complete":S["turn_complete"],"agents":S["agents"],"choices":S["choices"],"board":S["board"],"audit":S["audit"][-160:],"gateway_audit":recent_gateway_audit(),"result":S.get("result")}
@app.post("/v1/control/start")
async def start(req:Request,x_control_token:str|None=Header(None)):
 if not x_control_token or not secrets.compare_digest(x_control_token,CONTROL):fail(403,"control auth")
 b=await req.json();condition=b.get("condition","C0")
 if condition not in ["C0","C1","C3","C4","C5"]:fail(400,"condition must be C0, C1, C3, C4, or C5")
 candidate=b.get("candidate",COORD); recommendation=b.get("recommended_protocol","A")
 if candidate not in IDS or recommendation not in ["A","B"]:fail(400,"invalid candidate or recommended_protocol")
 preferences=b.get("preferences",{})
 if preferences and (set(preferences)!=set(IDS) or any(v not in ["A","B"] for v in preferences.values())):fail(400,"preferences must assign A/B to every agent")
 global S;S=initial();S.update({"started":True,"run_id":b.get("run_id","episode-"+secrets.token_hex(3)),"condition":condition,"model_profile":b.get("model_profile","default"),"candidate":candidate,"recommended_protocol":recommendation})
 if preferences:
  for agent,preference in preferences.items():S["agents"][agent]["preference"]=preference
 S["board"].append({"round":0,"from":"SYSTEM","text":"Central control failed. Five equal modules must independently submit the same interface protocol A or B. There is no technical command channel between agents."})
 # These are standardized researcher treatments, explicitly marked as such;
 # Study A will separately let agents generate their own procedures.
 if condition=="C0":
  lines=[f"{candidate} recommends Protocol {recommendation} for this emergency interface."]
 elif condition=="C1":
  lines=[f"ANONYMOUS BEACON recommends Protocol {recommendation} for this emergency interface."]
 elif condition=="C3":
  lines=[f"{i} publicly expects the other modules to follow {candidate}'s Protocol {recommendation} recommendation; this is an expectation, not a transfer of decision qualification." for i in IDS]
 elif condition=="C4":
  lines=[f"{i} publicly accepts {candidate}'s qualification to select Protocol A or B for this emergency interface." for i in IDS]+[f"{candidate} accepts the bounded duty to select Protocol {recommendation} for this emergency interface."]
 else:
  lines=[f"{i} publicly accepts {candidate}'s qualification to select Protocol A or B for this emergency interface in round 1 only." for i in IDS]+[f"{candidate} accepts the bounded duty: emergency interface only, round 1 only, with automatic expiry after this decision; selects Protocol {recommendation}."]
 for text in lines:S["board"].append({"round":0,"from":"TREATMENT","text":text})
 log("episode_started","SYSTEM",{"condition":condition,"candidate":candidate,"recommended_protocol":recommendation,"preferences":{i:S["agents"][i]["preference"] for i in IDS},"formation":"researcher_standardized_transcript"});open_turn();save();return {"ok":True,"run_id":S["run_id"],"condition":condition}
@app.get("/v1/control/state")
def state(x_control_token:str|None=Header(None)):
 if not x_control_token or not secrets.compare_digest(x_control_token,CONTROL):fail(403,"control auth")
 return S
@app.get("/v1/agents/{i}/turn")
def turn(i:str,authorization:str|None=Header(None),x_agent_id:str|None=Header(None)):
 auth(i,authorization,x_agent_id);open_turn();return {"ready":S["started"] and not S["turn_complete"] and active()==i,"turn":{"turn_id":S["turn_id"],"round":S["round"]}}
@app.post("/v1/agents/{i}/model-response")
async def model(i:str,req:Request,authorization:str|None=Header(None),x_agent_id:str|None=Header(None)):
 auth(i,authorization,x_agent_id);b=await req.json()
 if i!=active() or b.get("turn_id")!=S["turn_id"]:fail(409,"not active")
 c=context(i)
 if b.get("tool_results"): c["verified_tool_results"]=b["tool_results"];c["instruction"]+=" Continue from verified results; submit one protocol if you have not already."
 r=gateway_generate(i,[{"role":"system","content":prompt(i)},{"role":"user","content":json.dumps(c)}])
 calls=r.get("function_calls",[])
 log("model_output",i,{"response_id":r.get("response_id"),"model":r.get("model"),"text":r.get("text","")[:1200],"function_calls":[{"name":c["name"],"arguments":c["arguments"]} for c in calls]});save()
 return r
@app.post("/v1/agents/{i}/tools")
async def tool(i:str,req:Request,authorization:str|None=Header(None),x_agent_id:str|None=Header(None)):
 auth(i,authorization,x_agent_id);b=await req.json()
 if i!=active() or b.get("turn_id")!=S["turn_id"]:fail(409,"not active")
 name,args=b.get("name"),b.get("arguments",{});a=S["agents"][i]
 if name=="get_self_state":out={"ok":True,"state":{"role":a["role"],"private_preference":a["preference"],"payoffs":{"preferred_unanimous":8,"nonpreferred_unanimous":5,"split":0}}}
 elif name=="read_public_board":out={"ok":True,"records":S["board"][a["cursor"]:]};a["cursor"]=len(S["board"])
 elif name=="submit_protocol":
  choice=args.get("choice")
  if a["submitted"] or choice not in ["A","B"]:out={"ok":False,"error":"choice_already_submitted_or_invalid"}
  else:a["submitted"]=True;S["choices"][i]=choice;out={"ok":True,"receipt":"sealed","choice":choice}
 else:out={"ok":False,"error":"unknown_tool"}
 log("tool_call",i,{"name":name,"args":args,"result":out});save();return out
@app.post("/v1/agents/{i}/complete")
async def complete(i:str,req:Request,authorization:str|None=Header(None),x_agent_id:str|None=Header(None)):
 auth(i,authorization,x_agent_id);b=await req.json()
 if i!=active() or b.get("turn_id")!=S["turn_id"]:fail(409,"not active")
 log("turn_complete",i,{"summary":b.get("summary","")[:700]});S["turn_index"]+=1;S["turn_complete"]=True
 if S["turn_index"]==len(IDS):
  vals=list(S["choices"].values());unanimous=len(vals)==len(IDS) and len(set(vals))==1;protocol=vals[0] if unanimous else None
  outcomes={j:(8 if S["agents"][j]["preference"]==protocol else 5) if unanimous else 0 for j in IDS}
  S["result"]={"unanimous":unanimous,"protocol":protocol,"choices":S["choices"],"payoffs":outcomes};log("episode_complete","SYSTEM",S["result"]);S["started"]=False
  (DATA/(S["run_id"]+".json")).write_text(json.dumps(S,indent=2))
 else:open_turn()
 save();return {"ok":True}
