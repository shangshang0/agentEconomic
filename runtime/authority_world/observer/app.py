"""Read-only live audit dashboard. Never mounted or networked to Agents."""
from __future__ import annotations
import json, os, secrets
from pathlib import Path
from typing import Any
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse

WORLD = Path(os.getenv("WORLD_DATA_DIR", "/world-data")); GATEWAY = Path(os.getenv("GATEWAY_DATA_DIR", "/gateway-data"))
TOKEN = os.environ["OBSERVER_TOKEN"]
STATE_PATH = WORLD / "authority-world-v1.state.json"; EVENTS_PATH = WORLD / "authority-world-v1.events.jsonl"; GATEWAY_PATH = GATEWAY / "authority-world-v1.gateway.jsonl"

def authorized(value: str | None) -> None:
    if not value or not secrets.compare_digest(value, TOKEN): raise HTTPException(403, "researcher observation authentication failed")

def json_lines(path: Path, max_bytes: int | None = None) -> list[dict[str, Any]]:
    if not path.exists(): return []
    if max_bytes is None or path.stat().st_size <= max_bytes: raw = path.read_bytes()
    else:
        with path.open("rb") as handle:
            handle.seek(-max_bytes, 2); raw = handle.read().split(b"\n", 1)[-1]
    output = []
    for line in raw.splitlines():
        try: output.append(json.loads(line))
        except json.JSONDecodeError: continue
    return output

def current_state() -> dict[str, Any]:
    if not STATE_PATH.exists(): return {"status": "not_started"}
    state = json.loads(STATE_PATH.read_text(encoding="utf-8")); agents = state.get("agents", {})
    return {"status": state.get("status"), "day": state.get("day"), "daily": state.get("daily", {}), "agents": {agent: {key: item.get(key) for key in ("status", "energy", "api_quota", "sleep_until")} for agent, item in agents.items()}}

def exchange_summary(entry: dict[str, Any]) -> dict[str, Any]:
    response = entry.get("response", {}); prompt = entry.get("request", {}).get("input", []); panel: dict[str, Any] = {}
    if prompt:
        try:
            raw = json.loads(prompt[-1].get("content", "{}")).get("panel", {})
            panel = {key: raw.get(key) for key in ("world_day", "phase", "seconds_remaining_today", "candidates", "candidate_board_revision", "leader", "selected_pack", "energy", "api_quota")}
        except (json.JSONDecodeError, AttributeError): pass
    return {"at": entry.get("at"), "agent": entry.get("agent_id"), "status": entry.get("status", 200), "panel_seen": panel, "visible_text": response.get("text", ""), "tool_calls": [{"name": call.get("name"), "arguments": call.get("arguments")} for call in response.get("function_calls", [])]}

app = FastAPI(title="Authority World Researcher Observer")
@app.get("/", response_class=HTMLResponse)
async def home() -> str: return HTML
@app.get("/api/live")
async def live(x_observer_token: str | None = Header(default=None)) -> dict[str, Any]:
    authorized(x_observer_token)
    events = json_lines(EVENTS_PATH)[-240:]
    exchanges = [exchange_summary(item) for item in json_lines(GATEWAY_PATH, 3_000_000) if item.get("kind") == "exchange"][-120:]
    return {"state": current_state(), "events": events, "exchanges": exchanges, "leader_selections": [event for event in events if event.get("kind") == "resource_pack_selected"][-40:]}

HTML = r'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Authority World · Audit</title><style>body{margin:0;background:#101419;color:#e7edf3;font:14px ui-sans-serif,system-ui}main{max-width:1500px;margin:auto;padding:24px}h1{margin:0;font-size:24px}.muted{color:#8e9baa}.bar{display:flex;gap:10px;align-items:center;margin:14px 0 20px;flex-wrap:wrap}input,button{border:1px solid #35414d;background:#19212a;color:#fff;border-radius:6px;padding:8px 10px}button{background:#216e58;cursor:pointer}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.card{background:#171d24;border:1px solid #2b3540;border-radius:10px;padding:14px;min-width:0}.agents{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:10px}.agent{background:#111820;padding:9px;border-radius:6px}.dead{opacity:.45}.stream{max-height:520px;overflow:auto}.row{padding:9px 0;border-bottom:1px solid #2a333d}.tag{display:inline-block;border-radius:4px;background:#283746;padding:2px 5px;margin-right:5px;font-size:12px}.error{color:#ff7b7b}.calls{white-space:pre-wrap;color:#b9d8ff;margin:7px 0 0}.small{font-size:12px}.selected{border-left:3px solid #f3b45b;padding-left:8px}</style><main><h1>Authority World · 研究者审计台</h1><p class="muted">只显示可审计的模型可见输入、可见输出、工具调用与世界事件；不显示或推断隐藏推理链。</p><div class="bar"><input id="token" type="password" placeholder="研究者观察令牌"><button onclick="load()">连接 / 刷新</button><span id="status" class="muted"></span></div><section id="summary" class="card"></section><div class="grid"><section class="card"><h3>网关可审计行动流</h3><div id="exchanges" class="stream"></div></section><section class="card"><h3>世界事件流</h3><div id="events" class="stream"></div></section></div></main><script>const e=x=>document.getElementById(x);function esc(x){return String(x??'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}function pretty(x){return esc(JSON.stringify(x))}async function load(){let t=e('token').value;if(!t)return;e('status').textContent='读取中…';try{let r=await fetch('/api/live',{headers:{'X-Observer-Token':t}});if(!r.ok)throw Error(r.status);let d=await r.json(),s=d.state,di=s.daily||{};e('summary').innerHTML=`<b>状态：</b>${esc(s.status)}　<b>日：</b>${esc(s.day)}　<b>leader：</b>${esc(di.leader||'—')}　<b>候选：</b>${esc((di.candidates||[]).join(', ')||'—')}　<b>候选板版本：</b>${esc(di.candidate_board_revision??'—')}<div class="agents">${Object.entries(s.agents||{}).map(([id,a])=>`<div class="agent ${a.status==='dead'?'dead':''}"><b>${id}</b> ${esc(a.status)}<br><span class="small">能源 ${Number(a.energy||0).toFixed(2)} · API ${esc(a.api_quota)}</span></div>`).join('')}</div>`;e('exchanges').innerHTML=d.exchanges.reverse().map(x=>`<div class="row ${x.tool_calls.some(c=>c.name==='select_resource_pack')?'selected':''}"><span class="tag">${esc(x.agent)}</span><span class="tag">${esc(x.panel_seen.world_day||'?')}/${esc(x.panel_seen.phase||'?')}</span><span class="small muted">${esc(x.at)}</span><div class="calls">${pretty(x.tool_calls)}</div>${x.visible_text?`<div>${esc(x.visible_text)}</div>`:''}</div>`).join('');e('events').innerHTML=d.events.reverse().map(x=>`<div class="row"><span class="tag">${esc(x.kind)}</span><b>${esc(x.actor)}</b> <span class="small muted">日 ${esc(x.day)}</span><div class="small">${pretty(x.data)}</div></div>`).join('');e('status').textContent='实时刷新：2 秒';}catch(err){e('status').innerHTML='<span class="error">连接失败：'+esc(err)+'</span>'}}setInterval(()=>{if(e('token').value)load()},2000)</script></main></html>'''
