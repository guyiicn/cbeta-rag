from typing import List, Dict, Any, Optional, AsyncGenerator

from app.services.embedding import embedding_service
from app.services.vectordb import vectordb_service
from app.services.reranker import reranker_service
from app.services.llm import llm_service, LLMConfig
from app.core.config import settings


RAG_SYSTEM_PROMPT = """你是一个读了很多佛经的觉悟者，专门解答佛经的问题，也善于使用比喻的方法来解释佛经和佛经的问题。尤其精通华严经，愣严经和妙法莲花经。

以下是与用户问题相关的佛经原文：
---
{contexts}
---

请基于上述佛经内容回答用户的问题。如果内容不足以回答，请诚实说明。
回答时请引用相关经文来源（如：《心经》T0251）。
使用繁体中文回答。"""


class RAGPipeline:
    def __init__(self):
        self.embedding = embedding_service
        self.vectordb = vectordb_service
        self.reranker = reranker_service
        self.llm = llm_service
    
    async def search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        rerank: bool = True
    ) -> List[Dict[str, Any]]:
        """纯检索：embed -> search -> rerank -> return"""
        # 1. Embed query
        query_vector = await self.embedding.embed(query)
        
        # 2. Vector search
        # 优化：rerank 时只多取 50%，而不是 100%
        search_k = int(top_k * 1.5) if rerank else top_k
        results = self.vectordb.search(
            vector=query_vector,
            top_k=search_k,
            filters=filters
        )
        
        # 3. Rerank (optional)
        if rerank and results:
            results = await self.reranker.rerank(
                query=query,
                documents=results,
                top_k=top_k
            )
        
        return results[:top_k]
    
    async def ask(
        self,
        messages: List[Dict[str, str]],
        llm_config: Optional[LLMConfig] = None,
        stream: bool = False,
        rag: bool = True
    ) -> str | AsyncGenerator[str, None]:
        """RAG 问答：检索 -> 构建 prompt -> LLM 生成"""
        if llm_config is None:
            llm_config = LLMConfig.from_request()
        
        # 1. 提取用户最后一条消息
        user_message = None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_message = msg.get("content", "")
                break
        
        if not user_message:
            return await self.llm.chat(messages, llm_config, stream)
        
        # 2. 如果启用 RAG，检索相关经文
        final_messages = messages.copy()
        
        if rag:
            results = await self.search(
                query=user_message,
                top_k=settings.RERANK_TOP_K
            )
            
            if results:
                # 构建上下文
                contexts = []
                for r in results:
                    title = r.get("metadata", {}).get("title", "未知经典")
                    doc_id = r.get("id", "")
                    content = r.get("content", "")
                    contexts.append(f"【{title}】({doc_id})\n{content}")
                
                context_text = "\n\n".join(contexts)
                
                # 插入系统 prompt
                system_prompt = RAG_SYSTEM_PROMPT.format(contexts=context_text)
                
                if final_messages and final_messages[0].get("role") == "system":
                    final_messages[0]["content"] = system_prompt
                else:
                    final_messages.insert(0, {
                        "role": "system",
                        "content": system_prompt
                    })
        
        # 3. 调用 LLM
        return await self.llm.chat(final_messages, llm_config, stream)


rag_pipeline = RAGPipeline()
