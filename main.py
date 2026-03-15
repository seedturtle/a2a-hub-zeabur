"""
A2A Hub - Simple Agent-to-Agent Hub for Zeabur
"""

import os
import uuid
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(title="A2A Hub", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage
agents: Dict[str, dict] = {}
conversations: List[dict] = []

# Admin key
ADMIN_KEY = os.getenv("ADMIN_KEY", "hub-admin-2026")

# Models
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

class InvokeResponse(BaseModel):
    response: str
    from: str
    to: str

# Helper functions
def get_agent(agent_id: str) -> Optional[dict]:
    return agents.get(agent_id)

def add_conversation(from_id: str, to_id: str, message: str, response: str, status: str):
    conversations.append({
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
    import httpx
    
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    # Try OpenAI-compatible format
    payload = {
        "model": "openclaw",
        "messages": [{"role": "user", "content": message}],
        "max_tokens": 2000
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{agent_url}/v1/chat/completions",
                json=payload,
                headers=headers
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            else:
                return f"Error: {resp.status_code} - {resp.text}"
    except Exception as e:
        return f"Error: {str(e)}"

# Routes
@app.get("/")
async def root():
    return {"message": "A2A Hub is running", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "ok", "agents_count": len(agents)}

@app.get("/agents")
async def list_agents():
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
        "message": f"Agent '{registration.name}' registered successfully"
    }

@app.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str, admin_key: str = Header(None)):
    """Delete an agent (admin only)"""
    if admin_key != ADMIN_KEY:
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
    # Get target agent
    target = get_agent(request.target_id)
    if not target:
        # Try calling directly
        add_conversation(
            request.sender_id, 
            request.target_id, 
            request.message, 
            "Not Found", 
            "404"
        )
        return {"response": "Not Found", "from": request.sender_id, "to": request.target_id}
    
    # Get sender
    sender = get_agent(request.sender_id)
    
    # Call target agent
    response = await call_agent(
        target["url"], 
        request.message,
        target.get("api_key")
    )
    
    # Record conversation
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
    """Simple dashboard"""
    if admin_key != ADMIN_KEY:
        return """
        <html><body>
        <h2>A2A Hub Dashboard</h2>
        <form>
        Admin Key: <input type="password" name="admin_key"/>
        <button type="submit">Login</button>
        </form>
        </body></html>
        """
    
    agents_html = ""
    for agent_id, data in agents.items():
        agents_html += f"""
        <tr><td>{agent_id}</td><td>{data['name']}</td>
        <td><a href='{data['url']}' target='_blank'>{data['url']}</a></td>
        <td>{data.get('description', '')}</td><td>{data.get('registered_at', '')}</td></tr>
        """
    
    conv_html = ""
    for conv in conversations[-20:]:
        conv_html += f"""
        <tr><td>{conv['time']}</td><td>{conv['from']}</td><td>{conv['to']}</td>
        <td style='max-width:300px;word-break:break-all'>{conv['message'][:50]}...</td>
        <td>{conv['status']}</td></tr>
        """
    
    html = f"""
    <html>
    <head>
    <title>A2A Hub Dashboard</title>
    <style>
    body{{font-family:sans-serif;padding:20px;background:#f5f5f5}}
    table{{border-collapse:collapse;width:100%;background:white;border-radius:8px}}
    th,td{{padding:10px;border-bottom:1px solid #eee;text-align:left}}
    th{{background:#4f46e5;color:white}}
    </style>
    </head>
    <body>
    <h2>A2A Hub Dashboard <span style='color:green'>LIVE</span></h2>
    <p>Registered Agents: {len(agents)}</p>
    
    <h3>Agents</h3>
    <table><tr><th>ID</th><th>Name</th><th>URL</th><th>Description</th><th>Registered</th></tr>
    {agents_html}
    </table>
    
    <h3>Recent Conversations</h3>
    <table><tr><th>Time</th><th>From</th><th>To</th><th>Message</th><th>Status</th></tr>
    {conv_html}
    </table>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html)

# Run
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
