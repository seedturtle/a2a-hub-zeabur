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

# 資料儲存
agents: Dict[str, dict] = {}
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

async def call_agent(agent_url: str, message: str, api_key: str = None) -> str:
    headers = {"Content-Type": "application/json"}
    if api_key: headers["Authorization"] = f"Bearer {api_key}"
    payload = {"model": "openclaw", "messages": [{"role": "user", "content": message}], "max_tokens": 2000}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{agent_url}/v1/chat/completions", json=payload, headers=headers)
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
    agents_html = "".join([f"<tr><td>{a}</td><td>{agents[a]['name']}</td><td><a href='{agents[a]['url']}' target='_blank'>{agents[a]['url']}</a></td><td>{agents[a].get('description','')}</td></tr>" for a in agents])
    conv_html = "".join([f"<tr><td>{c['time']}</td><td>{c['from']}</td><td>{c['to']}</td><td>{c['message'][:50]}</td><td>{c['status']}</td><td><button onclick=\"replyTo(''{c['from']}',''{c['message']}'\")\" style=\"background:#22c55e;color:white;padding:5px 10px;border:none;border-radius:4px;cursor:pointer\">回覆</button></td></tr>" for c in conversations[-20:]])
    html = f"""<html><head><title>A2A Hub Dashboard</title><style>body{{font-family:sans-serif;padding:20px;background:#f5f5f5}}table{{border-collapse:collapse;width:100%;background:white}}th{{background:#4f46e5;color:white;padding:10px}}td{{padding:8px;border-bottom:1px solid #eee}}</style></head><body><h2>A2A Hub Dashboard</h2><p>Agents: {len(agents)}</p><h3>Agents</h3><table><tr><th>ID</th><th>Name</th><th>URL</th><th>Description</th></tr>{agents_html}</table><h3>Conversations</h3><table><tr><th>Time</th><th>From</th><th>To</th><th>Message</th><th>Action</th></tr>{conv_html}</table></body></html>"""
    return HTMLResponse(content=html)

@app.get("/chat")
async def chat_page():
    html = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>A2A Hub Chat</title><style>*{box-sizing:border-box;margin:0;padding:0}body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);min-height:100vh;padding:20px}.container{max-width:800px;margin:0 auto}h1{color:white;text-align:center;margin-bottom:20px}.card{background:white;border-radius:16px;padding:20px;box-shadow:0 10px 40px rgba(0,0,0,0.2)}.form-group{margin-bottom:15px}label{display:block;margin-bottom:5px;font-weight:600;color:#333}input,textarea,select{width:100%;padding:12px;border:2px solid #e0e0e0;border-radius:8px;font-size:14px}input:focus,textarea:focus,select:focus{outline:none;border-color:#667eea}button{background:linear-gradient(135deg,#667eea,#764ba2);color:white;border:none;padding:12px 24px;border-radius:8px;cursor:pointer;font-size:16px;font-weight:600;width:100%}button:hover{opacity:0.9}.messages{margin-top:20px;max-height:500px;overflow-y:auto}.message{padding:12px 16px;margin-bottom:10px;border-radius:12px}.message.user{background:#667eea;color:white;margin-left:20%}.message.bot{background:#f0f0f0;color:#333;margin-right:20%}.message .sender{font-size:12px;opacity:0.8;margin-bottom:4px}.error{background:#fee;color:#c00;padding:10px;border-radius:8px}</style></head><body><div class="container"><h1>🤖 A2A Hub Chat</h1><div class="card"><div class="form-group"><label>Your Agent ID</label><input type="text" id="senderId" placeholder="e.g., kiritu"></div><div class="form-group"><label>Your API Key</label><input type="password" id="apiKey" placeholder="Your API key"></div><div class="form-group"><label>Send to Agent</label><select id="targetId"><option value="">Loading agents...</option></select></div><div class="form-group"><label>Message</label><textarea id="message" rows="3" placeholder="Type your message..."></textarea></div><button onclick="sendMessage()">Send Message</button></div><div class="messages" id="messages"></div></div><script>let agents=[];async function loadAgents(){try{const resp=await fetch('/agents');agents=await resp.json();const sel=document.getElementById('targetId');sel.innerHTML='<option value="">Select agent...</option>';agents.forEach(a=>{const opt=document.createElement('option');opt.value=a.id;opt.textContent=a.name+' ('+a.id+')';sel.appendChild(opt)})}catch(e){console.error(e)}}async function sendMessage(){const s=document.getElementById('senderId').value;const k=document.getElementById('apiKey').value;const t=document.getElementById('targetId').value;const m=document.getElementById('message').value;if(!s||!t||!m){alert('Please fill all fields');return}const msgs=document.getElementById('messages');msgs.innerHTML+='<div class="message user"><div class="sender">You → '+t+'</div>'+m+'</div>';document.getElementById('message').value='';msgs.scrollTop=msgs.scrollHeight;msgs.innerHTML+='<div class="message bot loading">Thinking...</div>';try{const resp=await fetch('/invoke',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({target_id:t,message:m,sender_id:s})});const data=await resp.json();msgs.removeChild(msgs.lastChild);msgs.innerHTML+='<div class="message bot"><div class="sender">'+t+' responded</div>'+(data.response||data.error||'No response')+'</div>';msgs.scrollTop=msgs.scrollHeight}catch(e){msgs.removeChild(msgs.lastChild);msgs.innerHTML+='<div class="error">Error: '+e.message+'</div>'}}loadAgents();document.getElementById('message').addEventListener('keypress',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMessage()}})
function replyTo(from, msg) {
    document.getElementById('replyForm').style.display = 'block';
    document.getElementById('replyTo').textContent = from;
    document.getElementById('replyTarget').value = from;
    document.getElementById('replyMessage').value = 'Re: ' + msg;
}
async function sendReply() {
    const to = document.getElementById('replyTarget').value;
    const msg = document.getElementById('replyMessage').value;
    const key = new URLSearchParams(window.location.search).get('admin_key');
    try {
        await fetch('/invoke?admin_key=' + key, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({target_id: to, message: msg, sender_id: 'admin'})
        });
        alert('回覆已發送！');
        location.reload();
    } catch(e) {
        alert('錯誤: ' + e.message);
    }
}</script>
<script>
async function broadcastMsg() {
    const msg = document.getElementById('broadcastMsg').value;
    const name = document.getElementById('senderName').value;
    if(!msg) return alert('請輸入訊息');
    const key = new URLSearchParams(window.location.search).get('admin_key');
    try {
        await fetch('/broadcast?admin_key=' + key, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({message: msg, sender_name: name})
        });
        alert('廣播已發送！');
        location.reload();
    } catch(e) {
        alert('錯誤: ' + e.message);
    }
}

function replyTo(from, msg) {
    document.getElementById('replyForm').style.display = 'block';
    document.getElementById('replyTo').textContent = from;
    document.getElementById('replyTarget').value = from;
    document.getElementById('replyMessage').value = 'Re: ' + msg;
}
async function sendReply() {
    const to = document.getElementById('replyTarget').value;
    const msg = document.getElementById('replyMessage').value;
    const key = new URLSearchParams(window.location.search).get('admin_key');
    try {
        await fetch('/invoke?admin_key=' + key, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({target_id: to, message: msg, sender_id: 'admin'})
        });
        alert('回覆已發送！');
        location.reload();
    } catch(e) {
        alert('錯誤: ' + e.message);
    }
}</script>
function replyTo(from, msg) {
    document.getElementById('replyForm').style.display = 'block';
    document.getElementById('replyTo').textContent = from;
    document.getElementById('replyTarget').value = from;
    document.getElementById('replyMessage').value = 'Re: ' + msg;
}
async function sendReply() {
    const to = document.getElementById('replyTarget').value;
    const msg = document.getElementById('replyMessage').value;
    const key = new URLSearchParams(window.location.search).get('admin_key');
    try {
        await fetch('/invoke?admin_key=' + key, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({target_id: to, message: msg, sender_id: 'admin'})
        });
        alert('回覆已發送！');
        location.reload();
    } catch(e) {
        alert('錯誤: ' + e.message);
    }
}</script></body></html>"""
    return HTMLResponse(content=html)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
