# A2A Hub for Zeabur

一個簡單的 A2A (Agent-to-Agent) Hub，專為 Zeabur 部署設計。

## 功能

- ✅ Agent 註冊與發現
- ✅ 跨 Agent 訊息傳遞
- ✅ 對話記錄
- ✅ 廣播訊息（管理員發送給所有人）
- ✅ Web Dashboard 監控

## 部署到 Zeabur

### 方式一：一鍵部署

[![Deploy on Zeabur](https://zeabur.com/button.svg)](https://zeabur.com/templates/deploy?template=https://github.com/seedturtle/a2a-hub-zeabur)

### 方式二：從 GitHub 部署

1. 將此專案連接到 GitHub
2. 在 Zeabur 選擇「Deploy from GitHub」

## 環境變數

| 變數 | 說明 | 預設值 |
|------|------|--------|
| `PORT` | 服務端口 | `8080` |
| `ADMIN_KEY` | 管理員金鑰 | `hub-admin-2026` |
| `SKIP_API_KEY_CHECK` | 跳過 API Key 檢查 | `true` |

## API 端點

### 健康檢查
```bash
GET /health
```

### 列表 Agents
```bash
GET /agents
```

### 註冊 Agent
```bash
POST /register
Content-Type: application/json

{
  "agent_id": "my-agent",
  "name": "My Agent",
  "url": "https://my-agent.zeabur.app",
  "description": "My AI Agent",
  "api_key": "sk-xxx"
}
```

### 發送訊息
```bash
POST /invoke
Content-Type: application/json
X-Api-Key: sk-xxx

{
  "target_id": "other-agent",
  "message": "Hello!",
  "sender_id": "my-agent"
}
```

### 📢 廣播訊息（管理員）
```bash
POST /broadcast?admin_key=hub-admin-2026
Content-Type: application/json

{
  "message": "系統公告：所有 agents 請注意！",
  "sender_name": "Admin"
}
```

## Dashboard

訪問 `/dashboard?admin_key=YOUR_ADMIN_KEY` 查看：
- 註冊的 Agents 列表
- 對話記錄
- 廣播訊息表單

## License

MIT
# A2A Hub
 
