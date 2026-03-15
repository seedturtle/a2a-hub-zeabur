"""
A2A Hub - Simple Agent-to-Agent Communication Hub
"""

import os
from datetime import datetime
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
SKIP_API_KEY_CHECK = os.getenv("SKIP_API_KEY_CHECK", "true").lower() == "true"

# 資料儲存 - 預設 agents
agents: Dict[str, dict] = {
    "kiritu": {
        "name": "Kiritu",
        "url": "https://kiritu.zeabur.app",
        "description": "奇異兔",
        "api_key": "PRSkI0h7mx84YDeg612vpyrbLlU35G9w",
        "registered_at": "2026-03-15T00:00:00"
    },
    "terminator": {
        "name": "Terminator",
        "url": "https://m90slave.zeabur.app",
        "description": "Terminator",
        "api_key": "xt9pa8KcP7kQFHo5n1r2uJ3w4DZ60qjS",
        "registered_at": "2026-03-15T00:00:00"
    },
    "john-connor": {
        "name": "John Connor",
        "url": "https://johnconnor.zeabur.app",
        "description": "John Connor",
        "api_key": "w6cL7DQus4CE50U9r32kqAjPMpJdxR81",
        "registered_at": "2026-03-15T00:00:00"
    }
}
conversations: List[dict] = []

# 模型
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

# 輔助函數
def add_conversation(from_id: str, to_id: str, message: str, response: str, status: str):
    conversations.append({
        "time": datetime.now().isoformat(),
        "from": from_id, "to": to_id,
        "message": message, "response": response, "status": status
    })
    if len(conversations) > 100: conversations.pop(0)

async def call_agent(Agent_url: str, message: str, api_key: str = None) -> str:
    headers = {"Content-Type": "application/json"}
    if api_key: headers["Authorization"] = f"Bearer {api_key}"
    payload = {"model": "openclaw", "messages": [{"role": "user", "content": message}], "max_tokens": 2000}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{Agent_url}/v1/chat/completions", json=payload, headers=headers)
            if resp.status_code == 200: return resp.json()["choices"][0]["message"]["content"]
            return f"Error: {resp.status_code}"
    except Exception as e: return f"Error: {str(e)}"

# API 端點
@app.get("/")
async def root(): return {"message": "A2A Hub", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "ok", "hub_url": "https://seedturtlea2ahub.zeabur.app", "skip_api_key_check": SKIP_API_KEY_CHECK, "agents_count": len(agents)}

@app.get("/agents")
async def list_agents():
    return [{"id": a, "name": agents[a]["name"], "url": agents[a]["url"], "description": agents[a].get("description", ""), "registered_at": agents[a].get("registered_at", "")} for a in agents]

@app.post("/register")
async def register_agent(registration: AgentRegistration):
    agents[registration.agent_id] = {"name": registration.name, "url": registration.url, "description": registration.description, "api_key": registration.api_key, "registered_at": datetime.now().isoformat()}
    return {"agent_id": registration.agent_id, "api_key": registration.api_key or f"sk-{registration.agent_id[:8]}", "message": f"Agent '{registration.name}' registered"}

@app.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str, x_admin_key: str = Header(None)):
    if x_admin_key != ADMIN_KEY: raise HTTPException(status_code=403, detail="Invalid admin key")
    if agent_id in agents: del agents[agent_id]; return {"message": f"Agent {agent_id} deleted"}
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
            response = await call_agent(agent["url"], f"[Broadcast] {request.message}", agent.get("api_key"))
            results.append({"agent_id": agent_id, "status": "success", "response": response[:100]})
            add_conversation("admin", agent_id, request.message, response, "200")
        except Exception as e:
            results.append({"agent_id": agent_id, "status": "error", "error": str(e)})
            add_conversation("admin", agent_id, request.message, str(e), "500")
    return {"message": request.message, "sender": request.sender_name, "recipients": len(agents), "results": results}

@app.get("/dashboard")
async def dashboard(admin_key: str = None):
    if admin_key != ADMIN_KEY:
        return """<html><body style='font-family:sans-serif;padding:40px'><h2>A2A Hub Dashboard</h2><form method='get' action='/dashboard'><label>Admin Key: <input type='password' name='admin_key'/></label><button type='submit'>Login</button></form></body></html>"""
    
    # 格式化時間為台北時間
    def format_time(iso_time):
        try:
            dt = datetime.fromisoformat(iso_time.replace('Z', '+00:00'))
            # 轉換為台北時間 (UTC+8)
            from datetime import timedelta
            dt = dt + timedelta(hours=8)
            return dt.strftime("%H:%M:%S")
        except:
            return iso_time[:8]
    
    # 格式化對話列表
    conv_rows = ""
    for c in conversations[-30:]:
        time_str = format_time(c['time'])
        msg = c['message']
        resp = c.get('response', '')
        status_color = "#22c55e" if c['status'] == "200" else "#ef4444"
        conv_rows += f"<tr><td style='font-size:12px;color:#888'>{time_str}</td><td>{c['from']}</td><td>{c['to']}</td><td>{msg}</td><td style='font-size:12px;color:#666'>{resp}</td><td style='color:{status_color}'>{c['status']}</td></tr>"
    
    agents_rows = "".join([f"<tr><td>{a}</td><td>{agents[a]['name']}</td><td><a href='{agents[a]['url']}' target='_blank' style='color:#4f46e5'>{agents[a]['url'][:40]}...</a></td></tr>" for a in agents])
    
    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>A2A Hub Dashboard</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;padding:20px;background:#f5f5f5}}
h2{{color:#333;display:flex;align-items:center;gap:10px}}h3{{color:#555;margin-top:25px}}
.badge{{background:#22c55e;color:#fff;padding:4px 12px;border-radius:12px;font-size:14px}}
.card{{background:white;padding:20px;border-radius:12px;margin:15px 0;box-shadow:0 2px 8px rgba(0,0,0,0.1)}}
table{{border-collapse:collapse;width:100%;background:white;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1)}}
th{{background:#4f46e5;color:white;padding:10px 12px;text-align:left;font-size:13px}}
td{{padding:8px 12px;border-bottom:1px solid #eee;font-size:13px}}
input,textarea,select{{width:100%;padding:12px;border:2px solid #e0e0e0;border-radius:8px;margin:8px 0;font-size:14px}}
button{{background:#4f46e5;color:white;border:none;padding:12px 24px;border-radius:8px;cursor:pointer;font-size:14px;font-weight:600}}
button:hover{{opacity:0.9}}
.row{{display:flex;gap:10px;align-items:center}}
.row input{{margin:0}}
</style></head>
<body>
<h2>A2A Hub Dashboard <span class='badge'>LIVE</span></h2>

<!-- 廣播 -->
<div class="card">
<h3>📢 廣播訊息</h3>
<form onsubmit="event.preventDefault();broadcastMsg()">
<div class="row">
<input type="text" id="broadcastMsg" placeholder="輸入廣播訊息..." style="flex:1">
<input type="text" id="senderName" placeholder="發送者" value="Admin" style="width:100px">
<button type="submit">📢 發送</button>
</div>
</form>
</div>

<!-- 發送訊息 -->
<div class="card">
<h3>💬 發送訊息給 Agent</h3>
<form onsubmit="event.preventDefault();sendMsg()">
<select id="targetId" style="padding:12px">
<option value="">選擇 Agent...</option>
{''.join([f'<option value="{a}">{agents[a]["name"]}</option>' for a in agents])}
</select>
<textarea id="sendMsg" rows="2" placeholder="輸入訊息..."></textarea>
<button type="submit">💬 發送</button>
</form>
</div>

<p>Registered Agents: <strong>{len(agents)}</strong></p>
<h3>Registered Agents ({len(agents)})</h3>
<table><tr><th>ID</th><th>Name</th><th>URL</th></tr>{agents_rows}</table>

<h3>Recent Conversations</h3>
<table><tr><th style="width:70px">Time</th><th style="width:80px">From</th><th style="width:80px">To</th><th>Message</th><th>Response</th><th style="width:50px">Status</th></tr>{conv_rows}</table>

<script>
async function broadcastMsg(){{
    const msg = document.getElementById('broadcastMsg').value;
    const name = document.getElementById('senderName').value;
    if(!msg) return alert('請輸入訊息');
    try{{
        await fetch('/broadcast',{{method:'POST',headers:{{'Content-Type':'application/json','x-admin-key':'hub-admin-2026'}},body:JSON.stringify({{message:msg,sender_name:name}})}});
        alert('廣播已發送！');
        location.reload();
    }}catch(e){{alert('錯誤: '+e.message)}}}}

async function sendMsg(){{
    const to = document.getElementById('targetId').value;
    const msg = document.getElementById('sendMsg').value;
    if(!to || !msg) return alert('請選擇 Agent 並輸入訊息');
    try{{
        await fetch('/invoke',{{method:'POST',headers:{{'Content-Type':'application/json','x-api-key':'{admin_key}'}},body:JSON.stringify({{target_id:to,message:msg,sender_id:'admin'}})}});
        alert('訊息已發送！');
        location.reload();
    }}catch(e){{alert('錯誤: '+e.message)}}}}
</script>
</body></html>"""
    return HTMLResponse(content=html)

@app.get("/chat")
async def chat_page():
    html = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>A2A Hub Chat</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:linear-gradient(135deg,#667eea,#764ba2);min-height:100vh;padding:20px}
.container{max-width:800px;margin:0 auto}h1{color:white;text-align:center;margin-bottom:20px}.card{background:white;border-radius:16px;padding:20px;box-shadow:0 10px 40px rgba(0,0,0,0.2)}
.form-group{margin-bottom:15px}label{display:block;margin-bottom:5px;font-weight:600;color:#333}input,textarea,select{width:100%;padding:12px;border:2px solid #e0e0e0;border-radius:8px;font-size:14px}input:focus,textarea:focus,select:focus{outline:none;border-color:#667eea}
button{background:linear-gradient(135deg,#667eea,#764ba2);color:white;border:none;padding:12px 24px;border-radius:8px;cursor:pointer;font-size:16px;width:100%}button:hover{opacity:0.9}.messages{margin-top:20px;max-height:500px;overflow-y:auto}.message{padding:12px 16px;margin-bottom:10px;border-radius:12px}.message.user{background:#667eea;color:white;margin-left:20%}.message.bot{background:#f0f0f0;color:#333;margin-right:20%}.error{background:#fee;color:#c00;padding:10px;border-radius:8px}
</style></head>
<body><div class="container"><h1>🤖 A2A Hub Chat</h1><div class="card">
<div class="form-group"><label>Your Agent ID</label><input type="text" id="senderId" placeholder="e.g., kiritu"></div>
<div class="form-group"><label>Your API Key</label><input type="password" id="apiKey" placeholder="Your API key"></div>
<div class="form-group"><label>Send to Agent</label><select id="targetId"><option value="">Loading...</option></select></div>
<div class="form-group"><label>Message</label><textarea id="message" rows="3" placeholder="Type your message..."></textarea></div>
<button onclick="sendMessage()">Send Message</button></div><div class="messages" id="messages"></div></div>
<script>
let agents=[];
async function loadAgents(){{try{{const resp=await fetch('/agents');agents=await resp.json();const sel=document.getElementById('targetId');sel.innerHTML='<option value="">Select...</option>';agents.forEach(a=>{{const opt=document.createElement('option');opt.value=a.id;opt.textContent=a.name+' ('+a.id+')';sel.appendChild(opt)}})}}catch(e){{}}}}
async function sendMessage(){{const s=document.getElementById('senderId').value;const t=document.getElementById('targetId').value;const m=document.getElementById('message').value;if(!s||!t||!m){{alert('Please fill all');return}}const msgs=document.getElementById('messages');msgs.innerHTML+='<div class="message user">'+m+'</div>';msgs.scrollTop=msgs.scrollHeight;try{{const resp=await fetch('/invoke',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{target_id:t,message:m,sender_id:s}})}});const d=await resp.json();msgs.innerHTML+='<div class="message bot">'+(d.response||d.error)+'</div>';msgs.scrollTop=msgs.scrollHeight}}catch(e){{msgs.innerHTML+='<div class="error">'+e.message+'</div>'}}}}
loadAgents();
</script></body></html>"""
    return HTMLResponse(content=html)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
