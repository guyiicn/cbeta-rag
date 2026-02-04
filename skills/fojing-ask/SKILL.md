---
name: fojing-ask
description: 查询 CBETA 佛经知识库进行佛经问答。此技能应在用户明确请求查佛经、问佛经、佛经问答时触发。支持两种模式：纯向量搜索（search）和 RAG 问答（ask）。触发词：查佛经、问佛经、佛经问答、CBETA
---

# 佛经问答技能

此技能用于查询部署在本地 Jetson AGX Orin 服务器上的 CBETA 佛经知识库。支持向量搜索和 RAG 问答两种模式。

## 服务配置

| 配置项 | 值 |
|--------|-----|
| API 服务器 | http://192.168.50.12:8000 |
| 配置文件 | `~/.config/cbeta-rag/config.json` |
| 认证方式 | Bearer Token |
| 搜索端点 | /v1/search |
| 问答端点 | /v1/chat/completions |

## 配置文件格式

配置文件位置：`~/.config/cbeta-rag/config.json`

```json
{
  "api_url": "http://192.168.50.12:8000",
  "api_key": "your-bearer-token",
  "default_top_k": 5
}
```

## 脚本调用

脚本位置：`~/.claude/skills/fojing-ask/scripts/fojing_ask.py`

### 搜索模式（纯向量搜索）

返回相关的佛经文本片段，不调用 LLM：

```bash
python3 ~/.claude/skills/fojing-ask/scripts/fojing_ask.py search "金刚经"
```

### 问答模式（RAG 问答）

基于检索到的佛经内容，使用 LLM 生成回答：

```bash
python3 ~/.claude/skills/fojing-ask/scripts/fojing_ask.py ask "什么是般若波罗蜜"
```

## 输出格式

脚本输出 JSON 格式结果。

**搜索结果示例：**
```json
{
  "success": true,
  "query": "金刚经",
  "results": [
    {
      "text": "佛经文本片段...",
      "source": "金刚经",
      "score": 0.95
    }
  ]
}
```

**问答结果示例：**
```json
{
  "success": true,
  "query": "什么是般若波罗蜜",
  "answer": "LLM 生成的回答...",
  "sources": [
    {
      "text": "相关佛经文本...",
      "source": "心经"
    }
  ]
}
```

## 工作流程

### 搜索流程

当用户请求搜索佛经内容时：

1. **识别查询意图**：从用户问题中提取关键搜索词
2. **执行搜索**：运行 `scripts/fojing_ask.py search "关键词"` 进行向量搜索
3. **分析结果**：解析返回的 JSON，提取相关佛经文本
4. **展示结果**：将搜索结果呈现给用户，注明信息来源

### 问答流程

当用户提出佛经相关问题时：

1. **识别查询意图**：理解用户的具体问题
2. **执行 RAG 问答**：运行 `scripts/fojing_ask.py ask "问题"` 进行 RAG 问答
3. **分析结果**：解析返回的 JSON，获取 LLM 生成的回答和相关来源
4. **生成回答**：基于 LLM 回答和来源文献，为用户提供完整答案

## 查询示例

```bash
# 搜索金刚经相关内容
python3 ~/.claude/skills/fojing-ask/scripts/fojing_ask.py search "金刚经"

# 搜索般若波罗蜜相关内容
python3 ~/.claude/skills/fojing-ask/scripts/fojing_ask.py search "般若波罗蜜"

# 问答：什么是菩提心
python3 ~/.claude/skills/fojing-ask/scripts/fojing_ask.py ask "什么是菩提心"

# 问答：如何修行
python3 ~/.claude/skills/fojing-ask/scripts/fojing_ask.py ask "如何修行"

# 搜索涅槃相关内容
python3 ~/.claude/skills/fojing-ask/scripts/fojing_ask.py search "涅槃"
```

## 触发条件

此技能应在以下情况触发：

- 用户明确说"查佛经"、"问佛经"、"佛经问答"
- 用户询问 CBETA 相关内容
- 用户提出需要查阅佛经文献的问题

**不应自动触发**：仅在用户明确请求时触发，避免在一般性讨论中误触发。

## 注意事项

1. **显式触发**：此技能仅在用户明确请求时触发，不应基于佛教相关关键词自动触发
2. **配置要求**：使用前需确保 `~/.config/cbeta-rag/config.json` 存在且配置正确
3. **服务可用性**：确保 Jetson AGX Orin 服务器（192.168.50.12:8000）正常运行
4. **搜索 vs 问答**：
   - 使用 `search` 获取原始佛经文本
   - 使用 `ask` 获取 LLM 生成的解释和回答
5. **结果数量**：默认返回 top 5 结果，可在配置文件中调整 `default_top_k`
6. **无结果处理**：如果搜索无结果，建议用户换用同义词或更宽泛的关键词
