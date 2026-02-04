# CBETA RAG 维护手册

## 日常维护

### 服务状态检查

```bash
# 1. 检查容器状态
docker compose ps

# 2. 健康检查
curl -s http://localhost:8000/health | python3 -m json.tool

# 3. 查看统计信息
curl -s http://localhost:8000/v1/stats \
  -H 'Authorization: Bearer cbeta-rag-secret-key-2024' | python3 -m json.tool

# 4. 检查 Ollama
curl -s http://localhost:11434/api/tags | python3 -c "import sys,json; print(f'Ollama 模型数: {len(json.load(sys.stdin)[\"models\"])}')"
```

### 日志查看

```bash
# API 服务日志
docker logs cbeta-api --tail 100 -f

# Qdrant 日志
docker logs cbeta-qdrant --tail 100

# 查看降级事件
docker logs cbeta-api 2>&1 | grep "降级"
```

### 服务重启

```bash
# 重启 API (不影响数据)
docker compose restart api

# 重启所有服务
docker compose restart

# 强制重建 API
docker compose up -d api --force-recreate
```

---

## 性能监控

### 响应时间基准

| 操作 | 正常范围 | 告警阈值 |
|------|---------|---------|
| 向量搜索 | <0.5s | >2s |
| Rerank | <1s | >3s |
| LLM 生成 (Gemini) | 5-15s | >30s |
| LLM 生成 (Ollama) | 20-40s | >60s |
| 总响应时间 | <20s | >60s |

### 性能测试

```bash
# 测试向量搜索
time curl -s 'http://localhost:8000/v1/search' \
  -H 'Authorization: Bearer cbeta-rag-secret-key-2024' \
  -H 'Content-Type: application/json' \
  -d '{"query": "般若", "top_k": 8, "rerank": false}'

# 测试完整 RAG
time curl -s 'http://localhost:8000/v1/chat/completions' \
  -H 'Authorization: Bearer cbeta-rag-secret-key-2024' \
  -H 'Content-Type: application/json' \
  -d '{"messages": [{"role": "user", "content": "什么是般若？"}], "rag": true}'
```

---

## 数据管理

### 备份

```bash
# 1. 备份向量数据
cd ~/code/cbeta-rag
tar -czvf backup-qdrant-$(date +%Y%m%d).tar.gz data/qdrant/

# 2. 备份配置
cp .env .env.backup.$(date +%Y%m%d)

# 3. 备份整个项目
tar -czvf cbeta-rag-backup-$(date +%Y%m%d).tar.gz \
  --exclude='data/qdrant' \
  ~/code/cbeta-rag/
```

### 恢复

```bash
# 1. 停止服务
docker compose down

# 2. 恢复数据
tar -xzvf backup-qdrant-YYYYMMDD.tar.gz -C ~/code/cbeta-rag/

# 3. 启动服务
docker compose up -d
```

### 重新导入数据

```bash
# 如果需要重新导入 (会覆盖现有数据)
docker exec -it cbeta-api python scripts/ingest_cbeta.py

# 监控导入进度
docker logs cbeta-api -f
```

---

## 配置管理

### 修改 LLM Provider

```bash
# 编辑 .env
vim ~/code/cbeta-rag/.env

# 修改默认 provider
# DEFAULT_PROVIDER=gemini  改为
# DEFAULT_PROVIDER=qwen

# 重启生效
docker compose up -d api --force-recreate
```

### 修改 RAG 参数

```bash
# 编辑 .env
# RERANK_TOP_K=8   # 增加引用数量
# DEFAULT_TOP_K=15 # 增加候选数量

# 重启生效
docker compose up -d api --force-recreate

# 验证
curl -s http://localhost:8000/v1/stats \
  -H 'Authorization: Bearer cbeta-rag-secret-key-2024' | grep top_k
```

### 修改 System Prompt

编辑文件: `app/core/rag.py`

```python
RAG_SYSTEM_PROMPT = """你是一个读了很多佛经的觉悟者...
# 修改此处
"""
```

重启生效: `docker compose up -d api --force-recreate`

---

## 故障排查

### 问题: 服务无响应

```bash
# 1. 检查容器状态
docker compose ps

# 2. 检查端口
netstat -tlnp | grep -E "8000|6333|11434"

# 3. 检查日志
docker logs cbeta-api --tail 50

# 4. 重启服务
docker compose restart
```

### 问题: LLM 调用失败

```bash
# 1. 检查日志中的错误
docker logs cbeta-api 2>&1 | grep -i error | tail -20

# 2. 测试 Ollama (降级)
curl http://localhost:11434/api/chat -d '{
  "model": "qwen3:8b",
  "messages": [{"role": "user", "content": "hello"}],
  "stream": false
}'

# 3. 测试远程 API (需要网络)
curl -I https://generativelanguage.googleapis.com

# 4. 检查 API Key
cat ~/code/cbeta-rag/.env | grep -E "API_KEY|GEMINI|QWEN|GLM"
```

### 问题: 向量搜索无结果

```bash
# 1. 检查向量数量
curl -s http://localhost:6333/collections/cbeta | python3 -c \
  "import sys,json; print(f'向量数: {json.load(sys.stdin)[\"result\"][\"points_count\"]}')"

# 2. 如果为 0，重新导入
docker exec -it cbeta-api python scripts/ingest_cbeta.py

# 3. 测试 Embedding 服务
curl http://localhost:11434/api/embeddings -d '{
  "model": "bge-m3:latest",
  "prompt": "测试"
}'
```

### 问题: 降级频繁

```bash
# 1. 检查降级日志
docker logs cbeta-api 2>&1 | grep "降级" | tail -20

# 2. 检查网络连接
ping -c 3 generativelanguage.googleapis.com
ping -c 3 dashscope.aliyuncs.com

# 3. 临时切换到稳定 provider
# 编辑 .env: DEFAULT_PROVIDER=qwen
docker compose up -d api --force-recreate
```

---

## 资源监控

### 磁盘空间

```bash
# 检查磁盘使用
df -h /home/nvidia/

# 检查项目大小
du -sh ~/code/cbeta-rag/
du -sh ~/code/cbeta-rag/data/qdrant/

# 清理 Docker 无用镜像
docker system prune -f
```

### 内存使用

```bash
# 系统内存
free -h

# 容器内存
docker stats --no-stream
```

---

## 定期维护清单

### 每日
- [ ] 检查健康状态: `curl http://localhost:8000/health`
- [ ] 查看错误日志: `docker logs cbeta-api 2>&1 | grep -i error`

### 每周
- [ ] 检查磁盘空间: `df -h`
- [ ] 清理 Docker: `docker system prune -f`
- [ ] 检查降级事件

### 每月
- [ ] 完整备份
- [ ] 检查 API Key 有效性
- [ ] 更新依赖 (如需要)

---

*最后更新: 2026-02-04*
