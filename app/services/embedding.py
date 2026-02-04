import httpx
from typing import List

from app.core.config import settings


class EmbeddingService:
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.EMBEDDING_MODEL
    
    async def embed(self, text: str) -> List[float]:
        """生成单个文本的 embedding"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text}
            )
            response.raise_for_status()
            return response.json()["embedding"]
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量生成 embeddings"""
        embeddings = []
        for text in texts:
            embedding = await self.embed(text)
            embeddings.append(embedding)
        return embeddings


embedding_service = EmbeddingService()
