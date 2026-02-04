# CBETA RAG API 参考文档

## 基础信息

| 项目 | 值 |
|------|-----|
| Base URL | `http://192.168.50.12:8000` |
| 认证方式 | Bearer Token |
| 内容类型 | application/json |

### 认证

所有 `/v1/*` 端点需要认证:

```bash
curl -H 'Authorization: Bearer your-api-key' ...
```

---

## 端点列表

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|------|
| GET | `/health` | 健康检查 | 否 |
| GET | `/v1/stats` | 系统统计 | 是 |
| GET | `/v1/providers` | Provider 列表 | 是 |
| GET | `/v1/models` | 模型列表 | 是 |
| POST | `/v1/search` | 向量检索 | 是 |
| POST | `/v1/chat/completions` | 聊天补全 | 是 |

---

## GET /health

健康检查，返回服务状态。

**请求:**
```bash
curl http://192.168.50.12:8000/health
```

**响应:**
```json
{
  "status": "ok",
  "services": {
    "qdrant": {
      "status": "ok",
      "vectors_count": 195750
    },
    "ollama": {
      "status": "ok",
      "models_count": 12,
      "embedding_model": "ok",
      "fallback_llm": "ok"
    },
    "default_llm": {
      "provider": "gemini",
      "configured": true,
      "base_url": "https://generativelanguage.googleapis.com/..."
    }
  },
  "fallback": {
    "enabled": true,
    "provider": "ollama",
    "model": "qwen3:8b",
    "available": true
  }
}
```

---

## GET /v1/stats

系统统计信息。

**请求:**
```bash
curl http://192.168.50.12:8000/v1/stats \
  -H 'Authorization: Bearer your-api-key'
```

**响应:**
```json
{
  "status": "ok",
  "collection": {
    "name": "cbeta",
    "vectors_count": 195750,
    "points_count": 193400,
    "status": "green"
  },
  "config": {
    "default_provider": "gemini",
    "rerank_top_k": 8,
    "default_top_k": 15,
    "configured_providers": ["qwen", "glm", "gemini", "ollama"],
    "fallback_provider": "ollama"
  }
}
```

---

## GET /v1/providers

列出所有可用的 LLM Providers。

**请求:**
```bash
curl http://192.168.50.12:8000/v1/providers \
  -H 'Authorization: Bearer your-api-key'
```

**响应:**
```json
{
  "providers": [
    {
      "name": "gemini",
      "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
      "default_model": "gemini-2.0-flash",
      "configured": true
    },
    {
      "name": "qwen",
      "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
      "default_model": "qwen-plus",
      "configured": true
    },
    {
      "name": "ollama",
      "base_url": "http://host.docker.internal:11434",
      "default_model": "qwen3:8b",
      "configured": true
    }
  ]
}
```

---

## POST /v1/search

向量检索佛经内容。

**请求:**
```bash
curl -X POST http://192.168.50.12:8000/v1/search \
  -H 'Authorization: Bearer your-api-key' \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "什么是般若",
    "top_k": 5,
    "rerank": true
  }'
```

**参数:**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| query | string | 是 | - | 搜索查询 |
| top_k | int | 否 | 10 | 返回数量 |
| rerank | bool | 否 | true | 是否重排序 |
| filters | object | 否 | null | 过滤条件 |

**响应:**
```json
{
  "results": [
    {
      "id": "T2008_47",
      "content": "般若者，唐言智慧也。一切處所，一切時中...",
      "metadata": {
        "title": "六祖大師法寶壇經",
        "canon": "T"
      },
      "score": 0.892
    },
    {
      "id": "T1509_35",
      "content": "菩薩以般若波羅蜜利智慧力故...",
      "metadata": {
        "title": "大智度論",
        "canon": "T"
      },
      "score": 0.856
    }
  ]
}
```

---

## POST /v1/chat/completions

聊天补全 (OpenAI 兼容)。

### 基本用法

```bash
curl -X POST http://192.168.50.12:8000/v1/chat/completions \
  -H 'Authorization: Bearer your-api-key' \
  -H 'Content-Type: application/json' \
  -d '{
    "messages": [
      {"role": "user", "content": "什么是般若？"}
    ],
    "rag": true
  }'
```

### 指定 Provider

```bash
curl -X POST http://192.168.50.12:8000/v1/chat/completions \
  -H 'Authorization: Bearer your-api-key' \
  -H 'Content-Type: application/json' \
  -d '{
    "llm": {"provider": "qwen"},
    "model": "qwen-max",
    "messages": [{"role": "user", "content": "什么是般若？"}],
    "rag": true
  }'
```

### 流式输出

```bash
curl -X POST http://192.168.50.12:8000/v1/chat/completions \
  -H 'Authorization: Bearer your-api-key' \
  -H 'Content-Type: application/json' \
  -d '{
    "messages": [{"role": "user", "content": "什么是般若？"}],
    "rag": true,
    "stream": true
  }'
```

### 自定义 API

```bash
curl -X POST http://192.168.50.12:8000/v1/chat/completions \
  -H 'Authorization: Bearer your-api-key' \
  -H 'Content-Type: application/json' \
  -d '{
    "llm": {
      "base_url": "https://your-api.com/v1",
      "api_key": "your-key"
    },
    "model": "your-model",
    "messages": [{"role": "user", "content": "你好"}],
    "rag": false
  }'
```

**请求参数:**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| messages | array | 是 | - | 消息列表 |
| rag | bool | 否 | true | 是否启用 RAG |
| stream | bool | 否 | false | 是否流式输出 |
| model | string | 否 | (provider 默认) | 模型名称 |
| llm | object | 否 | null | LLM 配置 |
| llm.provider | string | 否 | (DEFAULT_PROVIDER) | Provider 名称 |
| llm.base_url | string | 否 | (预设) | 自定义 API URL |
| llm.api_key | string | 否 | (预设) | 自定义 API Key |

**响应 (非流式):**
```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1770170000,
  "model": "gemini-2.0-flash",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "般若，梵語 Prajñā，意為「智慧」..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0
  }
}
```

**响应 (流式 SSE):**
```
data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1770170000,"model":"gemini-2.0-flash","choices":[{"index":0,"delta":{"content":"般若"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1770170000,"model":"gemini-2.0-flash","choices":[{"index":0,"delta":{"content":"，"},"finish_reason":null}]}

...

data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1770170000,"model":"gemini-2.0-flash","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

---

## 错误响应

### 认证错误 (401)

```json
{
  "detail": "Invalid API key"
}
```

### Provider 不存在 (400)

```json
{
  "error": {
    "message": "Provider 'unknown' 不存在。可用: openai, anthropic, deepseek, qwen, glm, gemini, openrouter, siliconflow, ollama",
    "type": "invalid_provider"
  }
}
```

### API Key 无效 (401)

```json
{
  "error": {
    "message": "API key 无效或已过期 (openai)",
    "type": "authentication_error",
    "provider": "openai"
  }
}
```

### 请求限流 (429)

```json
{
  "error": {
    "message": "请求过于频繁，请稍后重试 (gemini)",
    "type": "rate_limit_error",
    "provider": "gemini"
  }
}
```

### 连接错误 (503)

```json
{
  "error": {
    "message": "无法连接到 gemini API，请检查网络",
    "type": "connection_error",
    "provider": "gemini"
  }
}
```

---

## 降级响应

当远程 API 不可用时，自动降级到 Ollama，响应内容会包含提示:

```
[使用本地模型 qwen3:8b，原服务 gemini 暂时不可用]

般若者，智慧也...
```

---

## 可用 Providers

| Provider | 默认模型 | 说明 |
|----------|----------|------|
| `gemini` | gemini-2.0-flash | Google Gemini |
| `qwen` | qwen-plus | 阿里通义千问 |
| `glm` | glm-4-flash | 智谱清言 |
| `deepseek` | deepseek-chat | DeepSeek |
| `openai` | gpt-4o | OpenAI |
| `anthropic` | claude-sonnet-4-20250514 | Anthropic Claude |
| `openrouter` | anthropic/claude-sonnet-4 | OpenRouter |
| `siliconflow` | Qwen/Qwen2.5-72B-Instruct | 硅基流动 |
| `ollama` | qwen3:8b | 本地 Ollama |

---

## 代码示例

### Python

```python
import requests

API_URL = "http://192.168.50.12:8000"
API_KEY = "your-api-key"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# 问答
response = requests.post(
    f"{API_URL}/v1/chat/completions",
    headers=headers,
    json={
        "messages": [{"role": "user", "content": "什么是般若？"}],
        "rag": True
    }
)
print(response.json()["choices"][0]["message"]["content"])
```

### JavaScript

```javascript
const response = await fetch('http://192.168.50.12:8000/v1/chat/completions', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer your-api-key',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    messages: [{ role: 'user', content: '什么是般若？' }],
    rag: true
  })
});

const data = await response.json();
console.log(data.choices[0].message.content);
```

### curl (流式)

```bash
curl -N -X POST http://192.168.50.12:8000/v1/chat/completions \
  -H 'Authorization: Bearer your-api-key' \
  -H 'Content-Type: application/json' \
  -d '{"messages": [{"role": "user", "content": "什么是般若？"}], "rag": true, "stream": true}'
```

---

*最后更新: 2026-02-04*
