# CBETA RAG 部署指南

## 环境要求

### 硬件
| 项目 | 最低要求 | 推荐配置 |
|------|---------|---------|
| CPU | ARM64 / x86_64 | NVIDIA Jetson AGX Orin |
| 内存 | 16GB | 32GB+ |
| 存储 | 50GB | 100GB+ SSD |
| GPU | 可选 | NVIDIA GPU (加速 Embedding) |

### 软件
- Docker 20.10+
- Docker Compose v2+
- Ollama (用于 Embedding 和本地 LLM)

## 部署步骤

### 1. 准备 CBETA 数据

```bash
# 下载 CBETA 电子佛典 (如已有可跳过)
# 数据应放置在: /home/nvidia/cbeta/cbeta-text/
# 目录结构:
# cbeta-text/
# ├── T/          # 大正藏
# │   ├── T0001/
# │   │   ├── T0001.txt
# │   │   └── T0001.yaml
# │   └── ...
# ├── X/          # 卍续藏
# └── ...
```

### 2. 安装 Ollama

```bash
# Linux
curl -fsSL https://ollama.com/install.sh | sh

# 启动 Ollama 服务
sudo systemctl enable ollama
sudo systemctl start ollama

# 拉取必要模型
ollama pull bge-m3:latest          # Embedding 模型 (必须)
ollama pull qwen3:8b               # 本地 LLM (降级用)
```

### 3. 克隆项目

```bash
cd ~/code
# 如果是新部署，复制项目文件
# git clone <repo> cbeta-rag  # 或从备份恢复

cd cbeta-rag
```

### 4. 配置环境变量

```bash
cp .env.example .env
vim .env
```

**.env 配置说明:**

```bash
# API 认证密钥 (必须修改!)
API_KEY=your-secret-api-key-here

# 基础服务
OLLAMA_BASE_URL=http://host.docker.internal:11434
QDRANT_HOST=qdrant
QDRANT_PORT=6333

# 默认 LLM Provider
DEFAULT_PROVIDER=gemini  # 可选: gemini, qwen, glm, ollama

# LLM API Keys (根据使用的 provider 填写)
GEMINI_API_KEY=your-gemini-key
QWEN_API_KEY=your-qwen-key
GLM_API_KEY=your-glm-key
# DEEPSEEK_API_KEY=
# OPENAI_API_KEY=
# ANTHROPIC_API_KEY=

# RAG 参数
DEFAULT_TOP_K=15     # 向量搜索数量
RERANK_TOP_K=8       # 最终返回数量
```

### 5. 启动服务

```bash
# 构建并启动
docker compose up -d

# 查看日志
docker compose logs -f

# 验证服务
curl http://localhost:8000/health
```

### 6. 导入数据 (首次部署)

```bash
# 进入容器执行导入
docker exec -it cbeta-api python scripts/ingest_cbeta.py

# 或在宿主机执行 (需要 Python 环境)
cd ~/code/cbeta-rag
python scripts/ingest_cbeta.py
```

导入过程:
- 解析 21,956 个 CBETA 文档
- 分块 (200字/块, 50字重叠)
- 向量化 (BGE-M3, 1024维)
- 存入 Qdrant

预计耗时: 2-4 小时 (取决于硬件)

### 7. 验证部署

```bash
# 1. 健康检查
curl http://localhost:8000/health

# 期望输出:
# {
#   "status": "ok",
#   "services": {
#     "qdrant": {"status": "ok", "vectors_count": 195750},
#     "ollama": {"status": "ok", "models_count": 12}
#   },
#   "fallback": {"enabled": true, "available": true}
# }

# 2. 测试问答
curl -X POST 'http://localhost:8000/v1/chat/completions' \
  -H 'Authorization: Bearer your-api-key' \
  -H 'Content-Type: application/json' \
  -d '{"messages": [{"role": "user", "content": "什么是般若？"}], "rag": true}'
```

---

## Docker Compose 配置说明

```yaml
services:
  qdrant:
    image: qdrant/qdrant:latest
    container_name: cbeta-qdrant
    ports:
      - "6333:6333"
    volumes:
      - ./data/qdrant:/qdrant/storage  # 向量数据持久化
    restart: unless-stopped

  api:
    build: .
    container_name: cbeta-api
    ports:
      - "8000:8000"
    volumes:
      - /home/nvidia/cbeta:/data/cbeta:ro  # CBETA 原始数据
      - ./app:/app/app:ro                   # 代码热更新
    environment:
      - QDRANT_HOST=qdrant
      - OLLAMA_BASE_URL=http://host.docker.internal:11434
    env_file:
      - .env
    extra_hosts:
      - "host.docker.internal:host-gateway"  # 访问宿主机 Ollama
    dns:
      - 8.8.8.8  # 确保能访问外部 API
      - 8.8.4.4
    restart: unless-stopped
```

---

## 升级部署

```bash
cd ~/code/cbeta-rag

# 1. 备份数据
cp -r data/qdrant data/qdrant.bak.$(date +%Y%m%d)

# 2. 更新代码
git pull  # 或手动更新文件

# 3. 重建并重启
docker compose build api
docker compose up -d api

# 4. 验证
curl http://localhost:8000/health
```

---

## 常见问题

### Q: Ollama 无法连接

```bash
# 检查 Ollama 服务
sudo systemctl status ollama

# 检查端口
curl http://localhost:11434/api/tags

# 如果是 Docker 网络问题，确认 extra_hosts 配置
```

### Q: 向量数据丢失

```bash
# 检查 Qdrant 存储
ls -la data/qdrant/

# 重新导入
docker exec -it cbeta-api python scripts/ingest_cbeta.py
```

### Q: API Key 认证失败

```bash
# 检查 .env 配置
cat .env | grep API_KEY

# 重启服务使配置生效
docker compose up -d api
```

---

## 网络端口

| 端口 | 服务 | 说明 |
|------|------|------|
| 8000 | FastAPI | RAG API 服务 |
| 6333 | Qdrant | 向量数据库 |
| 11434 | Ollama | Embedding/LLM |

---

*最后更新: 2026-02-04*
