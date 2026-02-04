import httpx
import math
import asyncio
from typing import List, Dict, Any, Tuple

from app.core.config import settings


class RerankerService:
    """重排序服务 - 使用并行 embedding 计算相似度"""
    
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.EMBEDDING_MODEL
    
    async def _get_embedding(self, client: httpx.AsyncClient, text: str) -> List[float]:
        """获取文本的 embedding"""
        response = await client.post(
            f"{self.base_url}/api/embeddings",
            json={"model": self.model, "prompt": text}
        )
        response.raise_for_status()
        return response.json()["embedding"]
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot_product / (norm1 * norm2)
    
    async def _get_doc_embedding(
        self, 
        client: httpx.AsyncClient, 
        doc: Dict[str, Any], 
        idx: int
    ) -> Tuple[int, List[float], Dict[str, Any]]:
        """获取单个文档的 embedding，返回 (索引, embedding, 文档)"""
        content = doc.get("content", "")
        content_truncated = content[:500] if len(content) > 500 else content
        try:
            embedding = await self._get_embedding(client, content_truncated)
            return (idx, embedding, doc)
        except Exception:
            return (idx, [], doc)
    
    async def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """重排序文档 - 并行获取所有 embedding"""
        if not documents:
            return []
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                # 并行获取 query 和所有文档的 embedding
                tasks = [
                    self._get_embedding(client, query)  # query embedding
                ]
                
                # 添加所有文档的 embedding 任务
                for idx, doc in enumerate(documents):
                    tasks.append(self._get_doc_embedding(client, doc, idx))
                
                # 并行执行所有任务
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # 第一个结果是 query embedding
                query_embedding = results[0] if not isinstance(results[0], Exception) else []
                
                if not query_embedding:
                    # 如果 query embedding 失败，返回原始排序
                    return documents[:top_k]
                
                # 处理文档 embedding 结果
                scored_docs = []
                for result in results[1:]:
                    if isinstance(result, Exception):
                        continue
                    idx, doc_embedding, doc = result
                    
                    if doc_embedding:
                        similarity = self._cosine_similarity(query_embedding, doc_embedding)
                        original_score = doc.get("score", 0.5)
                        # 综合分数: 原始分数 * 0.3 + rerank 相似度 * 0.7
                        combined_score = original_score * 0.3 + similarity * 0.7
                    else:
                        combined_score = doc.get("score", 0)
                        similarity = 0
                    
                    scored_docs.append({
                        **doc,
                        "original_score": doc.get("score", 0),
                        "rerank_score": similarity,
                        "score": combined_score
                    })
                
                # 按综合分数排序
                scored_docs.sort(key=lambda x: x.get("score", 0), reverse=True)
                
                return scored_docs[:top_k]
            
        except Exception as e:
            print(f"Rerank failed: {e}, using original order")
            return documents[:top_k]


reranker_service = RerankerService()
