# CBETA 佛经知识库 RAG 系统

基于 CBETA 电子佛典的智能问答系统，采用 RAG (Retrieval-Augmented Generation) 架构。

## 项目概述

| 项目 | 说明 |
|------|------|
| **功能** | 佛经智能检索与问答 |
| **数据源** | CBETA 电子佛典 (21,956 经典) |
| **向量数** | 193,400 条 |
| **部署环境** | NVIDIA Jetson AGX Orin |
| **API 兼容** | OpenAI Chat Completions |

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        CBETA RAG 系统                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   用户请求 ──→ FastAPI ──→ RAG Pipeline                         │
│                              │                                  │
│              ┌───────────────┼───────────────┐                  │
│              ▼               ▼               ▼                  │
│        ┌─────────┐    ┌─────────┐    ┌─────────────┐           │
│        │ BGE-M3  │    │ Qdrant  │    │   Reranker  │           │
│        │Embedding│    │ 向量库   │    │   重排序    │           │
│        └─────────┘    └─────────┘    └─────────────┘           │
│              │               │               │                  │
│              └───────────────┼───────────────┘                  │
│                              ▼                                  │
│                     ┌───────────────┐                           │
│                     │   LLM 生成    │                           │
│                     │ Gemini/Qwen/  │                           │
│                     │ GLM/Ollama    │                           │
│                     └───────────────┘                           │
│                              │                                  │
│                              ▼                                  │
│                        返回带引用的回答                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 核心特性

- **多 LLM Provider 支持**: Gemini, Qwen, GLM, DeepSeek, OpenAI, Anthropic, Ollama
- **自动降级**: 远程 API 不可用时自动切换到本地 Ollama
- **并行 Rerank**: 优化的重排序，响应时间 <1秒
- **OpenAI 兼容 API**: 可直接对接现有工具

## 快速开始

```bash
# 1. 启动服务
cd ~/code/cbeta-rag
docker compose up -d

# 2. 测试 API
curl -X POST 'http://localhost:8000/v1/chat/completions' \
  -H 'Authorization: Bearer your-api-key' \
  -H 'Content-Type: application/json' \
  -d '{"messages": [{"role": "user", "content": "什么是般若？"}], "rag": true}'

# 3. 健康检查
curl http://localhost:8000/health
```

## 目录结构

```
cbeta-rag/
├── app/
│   ├── api/           # API 端点
│   │   ├── chat.py    # 聊天补全 API
│   │   ├── search.py  # 检索 API
│   │   ├── models.py  # 模型列表 API
│   │   └── health.py  # 健康检查
│   ├── core/          # 核心逻辑
│   │   ├── config.py  # 配置管理
│   │   ├── auth.py    # 认证
│   │   └── rag.py     # RAG 流水线
│   ├── services/      # 服务层
│   │   ├── embedding.py   # 向量化
│   │   ├── vectordb.py    # 向量数据库
│   │   ├── reranker.py    # 重排序
│   │   └── llm.py         # LLM 调用
│   ├── ingestion/     # 数据导入
│   │   ├── cbeta_parser.py  # CBETA 解析
│   │   └── chunker.py       # 文本分块
│   └── main.py        # 应用入口
├── scripts/
│   └── ingest_cbeta.py  # 导入脚本
├── data/
│   └── qdrant/        # 向量数据存储
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env
```

## 文档索引

| 文档 | 说明 |
|------|------|
| [DEPLOYMENT.md](./DEPLOYMENT.md) | 部署指南 |
| [MAINTENANCE.md](./MAINTENANCE.md) | 维护手册 |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 技术架构 |
| [API.md](./API.md) | API 参考 |

## 技术栈

- **后端**: FastAPI + Python 3.10
- **向量库**: Qdrant
- **Embedding**: BGE-M3 (via Ollama)
- **LLM**: Gemini / Qwen / GLM / Ollama
- **容器**: Docker + Docker Compose
- **硬件**: NVIDIA Jetson AGX Orin (61GB 内存)

## 许可证

内部使用

---

*最后更新: 2026-02-04*
