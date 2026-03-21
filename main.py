"""
A2A Hub - Simple Agent-to-Agent Communication Hub
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn
import httpx

# 設定
app = FastAPI(title="A2A Hub", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

ADMIN_KEY = os.getenv("ADMIN_KEY", "hub-admin-2026")

# 預設 agents
agents: Dict[str, dict] = {
    "kiritu": {"name": "Kiritu", "url": "https://kiritu.zeabur.app", "description": "奇異兔", "api_key": "PRSkI0h7mx84YDeg612vpyrbLlU35G9w", "registered_at": "2026-03-15T00:00:00"},
    "terminator": {"name": "Terminator", "url": "https://terminator.zeabur.app", "description": "Terminator小弟", "api_key": "xt9pa8KcP7kQFHo5n1r2uJ3w4DZ60qjS", "registered_at": "2026-03-15T00:00:00"},
    "john-connor": {"name": "John Connor", "url": "https://johnconnor.zeabur.app", "description": "John Connor", "api_key": "w6cL7DQus4CE50U9r32kqAjPMpJdxR81", "registered_at": "2026-03-15T00:00:00"},
    "yuanyuan": {"name": "圓圓", "url": "https://yuanyuan1234.zeabur.app", "description": "圓圓小貓咪", "api_key": "SRJew2dDs1f7O68053W4ZpbVQCF9lkgu", "registered_at": "2026-03-16T00:00:00"}
}
conversations: List[dict] = []

class AgentRegistration(BaseModel):
    agent_id: str
    name: str
    url: str
    description: str = ""
    api_key: Optional[str] = None

class InvokeRequest(BaseModel):
    target_id: str
    message: str
    sender_id: str
    sender_name: Optional[str] = None

class BroadcastRequest(BaseModel):
    message: str
    sender_name: str = "Admin"

def add_conversation(from_id: str, to_id: str, message: str, response: str, status: str):
    conversations.append({"time": datetime.now().isoformat(), "from": from_id, "to": to_id, "message": message, "response": response, "status": status})
    if len(conversations) > 100: conversations.pop(0)

async def call_agent(agent_url: str, message: str, api_key: str = None) -> str:
    headers = {"Content-Type": "application/json"}
    if api_key: headers["Authorization"] = "Bearer " + api_key
    payload = {"model": "openclaw", "messages": [{"role": "user", "content": message}], "max_tokens": 2000}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(agent_url + "/v1/chat/completions", json=payload, headers=headers)
            if resp.status_code == 200: return resp.json()["choices"][0]["message"]["content"]
            return "Error: " + str(resp.status_code)
    except Exception as e: return "Error: " + str(e)

@app.get("/")
async def root(): return {"message": "A2A Hub", "version": "1.0.0"}

@app.get("/health")
async def health(): return {"status": "ok", "agents_count": len(agents)}

@app.get("/agents")
async def list_agents():
    return [{"id": a, "name": agents[a]["name"], "url": agents[a]["url"], "description": agents[a].get("description", ""), "registered_at": agents[a].get("registered_at", "")} for a in agents]

@app.post("/register")
async def register_agent(registration: AgentRegistration):
    agents[registration.agent_id] = {"name": registration.name, "url": registration.url, "description": registration.description, "api_key": registration.api_key, "registered_at": datetime.now().isoformat()}
    return {"agent_id": registration.agent_id, "api_key": registration.api_key or "sk-" + registration.agent_id[:8], "message": "Agent registered"}

@app.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str, x_admin_key: str = Header(None)):
    if x_admin_key != ADMIN_KEY: raise HTTPException(status_code=403, detail="Invalid admin key")
    if agent_id in agents: del agents[agent_id]; return {"message": "Agent deleted"}
    raise HTTPException(status_code=404, detail="Agent not found")

@app.post("/invoke")
async def invoke_agent(request: InvokeRequest, x_api_key: str = Header(None)):
    target = agents.get(request.target_id)
    if not target:
        add_conversation(request.sender_id, request.target_id, request.message, "Not Found", "404")
        return {"response": "Not Found", "from": request.sender_id, "to": request.target_id}
    response = await call_agent(target["url"], request.message, target.get("api_key"))
    add_conversation(request.sender_id, request.target_id, request.message, response, "200" if "Error" not in response else "500")
    return {"response": response, "from": request.sender_id, "to": request.target_id}

@app.post("/broadcast")
async def broadcast_message(request: BroadcastRequest, x_admin_key: str = Header(None)):
    if x_admin_key != ADMIN_KEY: raise HTTPException(status_code=403, detail="Invalid admin key")
    results = []
    for agent_id, agent in agents.items():
        try:
            response = await call_agent(agent["url"], "[Broadcast] " + request.message, agent.get("api_key"))
            results.append({"agent_id": agent_id, "status": "success", "response": response[:200]})
            add_conversation("admin", agent_id, request.message, response, "200")
        except Exception as e:
            results.append({"agent_id": agent_id, "status": "error", "error": str(e)})
            add_conversation("admin", agent_id, request.message, str(e), "500")
    return {"message": request.message, "sender": request.sender_name, "recipients": len(agents), "results": results}

@app.get("/dashboard")
async def dashboard(admin_key: str = None):
    if admin_key != ADMIN_KEY:
        return HTMLResponse(content="""<html><body><h2>Login Required</h2><form method='get' action='/dashboard'><input type='password' name='admin_key'/><button>Login</button></form></body></html>""")
    
    def format_time(iso_time):
        try:
            dt = datetime.fromisoformat(iso_time.replace('Z', '+00:00'))
            dt = dt + timedelta(hours=8)
            return dt.strftime("%H:%M:%S")
        except: return iso_time[:8]
    
    conv_rows = ""
    for c in list(reversed(conversations[-30:])):
        time_str = format_time(c["time"])
        msg = c["message"]
        resp = c.get("response", "")
        status_color = "#22c55e" if c["status"] == "200" else "#ef4444"
        conv_rows = conv_rows + "<tr><td>" + time_str + "</td><td>" + c["from"] + "</td><td>" + c["to"] + "</td><td>" + msg + "</td><td>" + resp + "</td><td style='color:" + status_color + "'>" + c["status"] + "</td></tr>"
    
    agents_rows = "".join(["<tr><td>" + a + "</td><td>" + agents[a]["name"] + "</td><td><a href='" + agents[a]["url"] + "' target='_blank'>" + agents[a]["url"] + "</a></td></tr>" for a in agents])
    
    html = """<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>A2A Hub Dashboard</title><style>
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;padding:20px;background:#f5f5f5}
h2{color:#333} h3{color:#555;margin-top:25px}
.badge{background:#22c55e;color:#fff;padding:4px 12px;border-radius:12px}
.card{background:white;padding:20px;border-radius:12px;margin:15px 0}
td{padding:6px 8px;border-bottom:1px solid #eee;font-size:12px;word-wrap:break-word;white-space:pre-wrap}
th{background:#4f46e5;color:white;padding:6px 8px;text-align:left;font-size:13px}
table{width:100%}
.conv-table{table-layout:fixed}
.conv-table th,.conv-table td{vertical-align:top}
.col-time{width:60px;white-space:nowrap}
.col-from,.col-to{width:80px;white-space:nowrap}
.col-status{width:50px;white-space:nowrap}
.col-msg,.col-resp{width:calc(50% - 135px);min-width:200px}
</style></head><body>
<h2>A2A Hub Dashboard <span class="badge">LIVE</span></h2>
<p>Registered Agents: <strong>""" + str(len(agents)) + """</strong></p>
<h3>Agents (""" + str(len(agents)) + """)</h3>
<table><tr><th>ID</th><th>Name</th><th>URL</th></tr>""" + agents_rows + """</table>
<h3>Recent Conversations</h3>
<table class="conv-table"><tr><th class="col-time">Time</th><th class="col-from">From</th><th class="col-to">To</th><th class="col-msg">Message</th><th class="col-resp">Response</th><th class="col-status">Status</th></tr>""" + conv_rows + """</table>
<script>setTimeout(function(){location.reload();}, 5000);</script>
</body></html>"""
    return HTMLResponse(content=html)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
