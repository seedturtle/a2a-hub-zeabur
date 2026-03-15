# A2A Hub for Zeabur

一個簡單的 A2A (Agent-to-Agent) Hub，專為 Zeabur 部署設計。

## 功能

- Agent 註冊與發現
- 跨 Agent 訊息傳遞
- Agent 狀態追蹤
- OpenAI 相容格式支援

## 部署到 Zeabur

### 方式一：直接部署

1. 點擊下方按鈕：
[![Deploy on Zeabur](https://zeabur.com/button.svg)](https://zeabur.com/templates/XXXXXXXX)

2. 或將此專案連接到 GitHub，Zeabur 會自動偵測並部署

### 方式二：手動部署

```bash
# 安裝依賴
pip install -r requirements.txt

# 運行
python main.py
```

## 環境變數

| 變數 | 說明 | 預設值 |
|------|------|--------|
| `PORT` | 服務端口 | `8080` |
| `ADMIN_KEY` | 管理員金鑰 | `your-admin-key` |
| `OPENAI_API_KEY` | OpenAI API Key | - |

## API 端點

### 健康檢查
```bash
GET /health
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

### 列表 Agents
```bash
GET /agents
```

## 使用範例

### 註冊 Agent
```bash
curl -X POST https://your-hub.zeabur.app/register \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "kiritu",
    "name": "Kiritu",
    "url": "https://kiritu.zeabur.app",
    "description": "奇異兔 AI Agent",
    "api_key": "sk-your-key"
  }'
```

### 發送訊息
```bash
curl -X POST https://your-hub.zeabur.app/invoke \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: sk-your-key" \
  -d '{
    "target_id": "terminator",
    "message": "Hello from kiritu!",
    "sender_id": "kiritu"
  }'
```

## License

MIT
