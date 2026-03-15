"""
A2A Hub - Simple Agent-to-Agent Communication Hub
專為 Zeabur 部署設計的簡單 A2A Hub
"""

import os
import uuid
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import uvicorn
import httpx
import asyncio

# ============== 設定 ==============
app = FastAPI(title="A2A Hub", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 環境變數
ADMIN_KEY = os.getenv("ADMIN_KEY", "hub-admin-2026")
SKIP_API_KEY_CHECK = os.getenv("SKIP_API_KEY_CHECK", "true").lower() == "true"

# ============== 資料儲存 ==============
agents: Dict[str, dict] = {}
conversations: List[dict] = []
conversation_id_counter = 0

# ============== 模型 ==============
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

class Agent(BaseModel):
    id: str
    name: str
    url: str
    description: str
    registered_at: str

# ============== 輔助函數 ==============
def get_agent(agent_id: str) -> Optional[dict]:
    return agents.get(agent_id)

def add_conversation(from_id: str, to_id: str, message: str, response: str, status: str):
    global conversation_id_counter
    conversation_id_counter += 1
    conversations.append({
        "id": conversation_id_counter,
        "time": datetime.now().isoformat(),
        "from": from_id,
        "to": to_id,
        "message": message,
        "response": response,
        "status": status
    })
    # Keep only last 100
    if len(conversations) > 100:
        conversations.pop(0)

async def call_agent(agent_url: str, message: str, api_key: str = None) -> str:
    """Call an agent via OpenAI-compatible API"""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    payload = {
        "model": "openclaw",
        "messages": [{"role": "user", "content": message}],
        "max_tokens": 2000
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Try /v1/chat/completions first
            resp = await client.post(
                f"{agent_url}/v1/chat/completions",
                json=payload,
                headers=headers
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            
            # Try /a2a endpoint
            resp = await client.post(
                f"{agent_url}/a2a",
                json={"message": message},
                headers=headers
            )
            if resp.status_code == 200:
                return resp.json().get("response", "OK")
            
            return f"Error: {resp.status_code}"
    except Exception as e:
        return f"Error: {str(e)}"

# ============== API 端點 ==============
@app.get("/")
async def root():
    return {"message": "A2A Hub is running", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {
        "status": "ok", 
        "hub_url": "https://a2a-hub.zeabur.app",
        "skip_api_key_check": SKIP_API_KEY_CHECK,
        "agents_count": len(agents)
    }

@app.get("/.well-known/agent-card.json")
async def agent_card():
    """A2A Agent Card"""
    return {
        "name": "A2A Hub",
        "description": "Central hub for agent-to-agent communication",
        "url": "https://a2a-hub.zeabur.app",
        "version": "1.0.0",
        "capabilities": {"streaming": False}
    }

@app.get("/agents", response_model=List[dict])
async def list_agents():
    """List all registered agents"""
    return [
        {
            "id": agent_id,
            "name": data["name"],
            "url": data["url"],
            "description": data.get("description", ""),
            "registered_at": data.get("registered_at", "")
        }
        for agent_id, data in agents.items()
    ]

@app.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    """Get agent details"""
    agent = agents.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {
        "id": agent_id,
        "name": agent["name"],
        "url": agent["url"],
        "description": agent.get("description", ""),
        "registered_at": agent.get("registered_at", "")
    }

@app.post("/register")
async def register_agent(registration: AgentRegistration):
    """Register a new agent"""
    agents[registration.agent_id] = {
        "name": registration.name,
        "url": registration.url,
        "description": registration.description,
        "api_key": registration.api_key,
        "registered_at": datetime.now().isoformat()
    }
    
    return {
        "agent_id": registration.agent_id,
        "api_key": registration.api_key or f"sk-{registration.agent_id[:8]}",
        "message": f"Agent '{registration.name}' registered successfully"
    }

@app.patch("/agents/{agent_id}")
async def update_agent(agent_id: str, registration: AgentRegistration):
    """Update agent info"""
    if agent_id not in agents:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    agents[agent_id].update({
        "name": registration.name,
        "url": registration.url,
        "description": registration.description,
        "api_key": registration.api_key,
    })
    
    return {"message": f"Agent {agent_id} updated"}

@app.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str, x_admin_key: str = Header(None)):
    """Delete an agent"""
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin key")
    
    if agent_id in agents:
        del agents[agent_id]
        return {"message": f"Agent {agent_id} deleted"}
    raise HTTPException(status_code=404, detail="Agent not found")

@app.post("/invoke")
async def invoke_agent(
    request: InvokeRequest,
    x_api_key: Optional[str] = Header(None)
):
    """Send message to another agent"""
    global conversation_id_counter
    
    # 驗證 API Key
    if not SKIP_API_KEY_CHECK and x_api_key:
        # 簡單驗證：檢查是否是有效的 agent key
        valid = False
        for agent in agents.values():
            if agent.get("api_key") == x_api_key:
                valid = True
                break
        if not valid and x_api_key != ADMIN_KEY:
            # 仍然允許通過，但記錄
            pass
    
    # 獲取目標 Agent
    target = get_agent(request.target_id)
    if not target:
        add_conversation(request.sender_id, request.target_id, request.message, "Not Found", "404")
        return {"response": "Not Found", "from": request.sender_id, "to": request.target_id}
    
    # 調用目標 Agent
    response = await call_agent(
        target["url"], 
        request.message,
        target.get("api_key")
    )
    
    # 記錄對話
    add_conversation(
        request.sender_id,
        request.target_id,
        request.message,
        response,
        "200" if "Error" not in response else "500"
    )
    
    return {
        "response": response,
        "from": request.sender_id,
        "to": request.target_id
    }

@app.get("/dashboard")
async def dashboard(admin_key: str = None):
    """Simple HTML dashboard"""
    if admin_key != ADMIN_KEY:
        return """
        <html><body style='font-family:sans-serif;padding:40px'>
        <h2>A2A Hub Dashboard</h2>
        <form method='get' action='/dashboard'>
        <label>Admin Key: <input type='password' name='admin_key'/></label>
        <button type='submit'>Login</button>
        </form></body></html>
        """
    
    # Agents HTML
    agents_html = ""
    for agent_id, data in agents.items():
        agents_html += f"""
        <tr><td>{agent_id}</td><td>{data['name']}</td>
        <td><a href='{data['url']}' target='_blank'>{data['url']}</a></td>
        <td>{data.get('description', '')}</td><td>{data.get('registered_at', '')}</td></tr>
        """
    
    if not agents_html:
        agents_html = "<tr><td colspan='5'>No agents registered</td></tr>"
    
    # Conversations HTML
    conv_html = ""
    for conv in conversations[-20:]:
        msg = conv['message'][:50] + "..." if len(conv['message']) > 50 else conv['message']
        status_color = "green" if conv['status'] == "200" else "red"
        conv_html += f"""
        <tr><td>{conv['time']}</td><td>{conv['from']}</td><td>{conv['to']}</td>
        <td style='max-width:300px;word-break:break-all'>{msg}</td>
        <td style='color:{status_color}'>{conv['status']}</td></tr>
        """
    
    if not conv_html:
        conv_html = "<tr><td colspan='5'>No conversations yet</td></tr>"
    
    html = f"""
    <html>
    <head>
    <title>A2A Hub Dashboard</title>
    <style>
    body{{font-family:sans-serif;padding:20px;background:#f5f5f5}}
    h2{{color:#333}} h3{{color:#555}}
    table{{border-collapse:collapse;width:100%;background:white;border-radius:8px;overflow:hidden;box-shadow:0 1px 4px #0001}}
    th{{background:#4f46e5;color:white;padding:10px 12px;text-align:left}}
    td{{padding:8px 12px;border-bottom:1px solid #eee;font-size:13px}}
    tr:last-child td{{border-bottom:none}}
    .badge{{background:#22c55e;color:#fff;border-radius:12px;padding:2px 10px;font-size:12px}}
    </style>
    </head>
    <body>
    <h2>A2A Hub Dashboard <span class='badge'>LIVE</span> <span style='background:#f59e0b;color:#fff;border-radius:12px;padding:2px 10px;font-size:12px;margin-left:8px'>⚠ SKIP_KEY_CHECK {SKIP_API_KEY_CHECK}</span></h2>
    <p>Hub URL: <strong>https://a2a-hub.zeabur.app</strong></p>
    <p>Registered Agents: <strong>{len(agents)}</strong></p>
    
    <h3>Registered Agents ({len(agents)})</h3>
    <table><tr><th>ID</th><th>Name</th><th>URL</th><th>Description</th><th>Registered At</th></tr>
    {agents_html}
    </table>
    
    <h3>Recent Conversations (last 20)</h3>
    <table><tr><th>Time</th><th>From</th><th>To</th><th>Message</th><th>Status</th></tr>
    {conv_html}
    </table>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html)

# ============== 啟動 ==============
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
