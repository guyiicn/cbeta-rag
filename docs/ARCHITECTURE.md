# CBETA RAG 技术架构文档

## 系统概览

### 部署环境

| 项目 | 配置 |
|------|------|
| 设备 | NVIDIA Jetson AGX Orin |
| OS | Linux 5.15.148-tegra (L4T R36.4.3) |
| 架构 | ARM64 (aarch64) |
| 内存 | 61GB 统一内存 |
| 存储 | NVMe SSD |

### 服务组件

```
┌─────────────────────────────────────────────────────────────────┐
│                         宿主机 (Jetson)                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐     ┌─────────────────────────────────────┐   │
│  │   Ollama    │     │         Docker Network              │   │
│  │  :11434     │     │  ┌───────────┐  ┌───────────────┐   │   │
│  │             │◄────┼──│ cbeta-api │  │ cbeta-qdrant  │   │   │
│  │ - bge-m3    │     │  │  :8000    │  │    :6333      │   │   │
│  │ - qwen3:8b  │     │  └───────────┘  └───────────────┘   │   │
│  └─────────────┘     └─────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    数据存储                              │   │
│  │  /home/nvidia/cbeta/          - CBETA 原始文本          │   │
│  │  /home/nvidia/code/cbeta-rag/data/qdrant/ - 向量数据    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 数据流架构

### RAG 检索流程

```
用户问题: "什么是般若？"
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 1. Query Embedding (BGE-M3)                                     │
│    "什么是般若？" → [0.12, -0.34, 0.56, ...] (1024维)           │
│    耗时: ~0.2秒                                                 │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. Vector Search (Qdrant)                                       │
│    从 193,400 条向量中检索 Top 12 (RERANK_TOP_K × 1.5)          │
│    使用 Cosine 相似度                                           │
│    耗时: ~0.1秒                                                 │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. Rerank (并行 Embedding 相似度)                               │
│    对 12 条候选文档并行计算相似度                                │
│    返回 Top 8 最相关结果                                        │
│    耗时: ~0.5秒                                                 │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. Context Assembly                                             │
│    构建 System Prompt:                                          │
│    "你是一个觉悟者... 以下是相关佛经原文:                        │
│     【六祖壇經】(T2008) 般若是智慧...                           │
│     【大智度論】(T1509) 般若波羅蜜..."                          │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. LLM Generation                                               │
│    ┌─────────────────────────────────────────────────────────┐ │
│    │ Primary: Gemini/Qwen/GLM (远程 API)                     │ │
│    │ 耗时: ~5-15秒                                           │ │
│    └─────────────────────────────────────────────────────────┘ │
│              │ 失败时自动降级                                   │
│              ▼                                                  │
│    ┌─────────────────────────────────────────────────────────┐ │
│    │ Fallback: Ollama qwen3:8b (本地)                        │ │
│    │ 耗时: ~30秒                                             │ │
│    └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
返回带引用的回答
```

---

## 核心模块

### 1. 配置管理 (app/core/config.py)

```python
# 预设 LLM Providers
PRESET_PROVIDERS = {
    "gemini": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai", ...},
    "qwen": {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", ...},
    "glm": {"base_url": "https://open.bigmodel.cn/api/paas/v4", ...},
    "ollama": {"base_url": "http://host.docker.internal:11434", ...},
    ...
}

# 关键配置项
class Settings:
    DEFAULT_PROVIDER: str = "gemini"
    RERANK_TOP_K: int = 8      # 返回给 LLM 的文档数
    DEFAULT_TOP_K: int = 15    # 向量搜索数量
    CHUNK_SIZE: int = 200      # 文本块大小
    CHUNK_OVERLAP: int = 50    # 块重叠
```

### 2. LLM 服务 (app/services/llm.py)

**降级机制:**

```python
# 触发降级的错误
FALLBACK_ERRORS = (ConnectError, ConnectTimeout, ReadTimeout, ...)
FALLBACK_STATUS_CODES = {429, 500, 502, 503, 504}

async def chat(messages, config, stream, allow_fallback=True):
    try:
        return await _call_llm(messages, config, stream)
    except FALLBACK_ERRORS:
        if allow_fallback:
            fallback_config = config.to_fallback()  # 切换到 Ollama
            return await _call_llm(messages, fallback_config, stream)
        raise
```

**支持的 API 格式:**
- OpenAI 兼容 (Gemini, Qwen, GLM, DeepSeek, OpenRouter, SiliconFlow)
- Anthropic (Claude)
- Ollama (本地)

### 3. Reranker (app/services/reranker.py)

**并行优化实现:**

```python
async def rerank(query, documents, top_k):
    async with httpx.AsyncClient() as client:
        # 并行获取所有 embedding
        tasks = [get_embedding(client, query)]
        for doc in documents:
            tasks.append(get_doc_embedding(client, doc))
        
        results = await asyncio.gather(*tasks)  # 并行执行
        
        # 计算综合分数
        # score = original_score * 0.3 + cosine_similarity * 0.7
```

### 4. 向量数据库 (app/services/vectordb.py)

```python
# Qdrant 配置
collection_name = "cbeta"
vector_dim = 1024
distance = Distance.COSINE

# 搜索
results = client.query_points(
    collection_name="cbeta",
    query=query_vector,
    limit=top_k,
    with_payload=True
)
```

---

## 数据模型

### CBETA 文档结构

```python
@dataclass
class CBETADocument:
    id: str           # e.g., "T0251"
    title: str        # e.g., "般若波羅蜜多心經"
    content: str      # 经文全文
    canon: str        # 藏经分类 (T=大正藏, X=卍续藏)
    source: str
    publish_date: str
    contributors: str
```

### 向量 Payload 结构

```json
{
  "doc_id": "T0251_chunk_001",
  "content": "觀自在菩薩行深般若波羅蜜多時...",
  "title": "般若波羅蜜多心經",
  "canon": "T",
  "chunk_index": 1
}
```

### API 请求/响应

**Chat Completions (OpenAI 兼容):**

```json
// Request
{
  "messages": [{"role": "user", "content": "什么是般若？"}],
  "rag": true,
  "llm": {"provider": "gemini"},
  "model": "gemini-2.0-flash",
  "stream": false
}

// Response
{
  "id": "chatcmpl-xxx",
  "model": "gemini-2.0-flash",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "般若者，智慧也..."
    },
    "finish_reason": "stop"
  }]
}
```

---

## 性能指标

### 响应时间分解

| 阶段 | 耗时 | 占比 |
|------|------|------|
| Query Embedding | 0.2s | 2% |
| Vector Search | 0.1s | 1% |
| Rerank (并行) | 0.5s | 5% |
| LLM Generation | 9s | 92% |
| **总计** | **~10s** | 100% |

### 资源占用

| 服务 | 内存 | CPU |
|------|------|-----|
| cbeta-api | ~500MB | 低 |
| cbeta-qdrant | ~2GB | 低 |
| Ollama (空闲) | ~1GB | 低 |
| Ollama (推理) | ~8GB | 高 |

---

## 安全设计

### 认证

- Bearer Token 认证 (API_KEY)
- 所有数据接口需认证
- /health 端点公开

### 降级保护

- 远程 API 不可用时自动降级到本地 Ollama
- 降级响应带明确提示
- 保证 100% 可用性

### 数据安全

- CBETA 数据只读挂载
- 向量数据本地持久化
- API Key 存储在 .env (不提交版本控制)

---

## 扩展设计

### 添加新 LLM Provider

1. 在 `config.py` 的 `PRESET_PROVIDERS` 添加配置
2. 在 `Settings` 类添加 API Key 字段
3. 在 `get_api_key()` 方法添加映射
4. 如果 API 格式特殊，在 `llm.py` 添加专用处理方法

### 添加新数据源

1. 在 `app/ingestion/` 创建新解析器
2. 实现与 `CBETADocument` 兼容的数据结构
3. 创建导入脚本

### 水平扩展

- Qdrant 支持分布式部署
- API 服务可多实例部署 (需外部负载均衡)
- Ollama 可独立部署

---

*最后更新: 2026-02-04*
