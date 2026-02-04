from typing import List, Optional, Dict, Any
import hashlib
from qdrant_client import QdrantClient, models
from qdrant_client.http.models import Distance, VectorParams, PointStruct

from app.core.config import settings


class VectorDBService:
    def __init__(self):
        self.client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT
        )
        self.collection_name = settings.COLLECTION_NAME
        self.vector_dim = settings.VECTOR_DIM
    
    def _string_to_int_id(self, string_id: str) -> int:
        """将字符串 ID 转换为整数 ID"""
        hash_bytes = hashlib.md5(string_id.encode()).digest()
        return int.from_bytes(hash_bytes[:8], byteorder="big") & 0x7FFFFFFFFFFFFFFF
    
    def create_collection(self) -> bool:
        """创建集合（如果不存在）"""
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)
        
        if not exists:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_dim,
                    distance=Distance.COSINE
                )
            )
            return True
        return False
    
    def upsert_documents(
        self,
        ids: List[str],
        vectors: List[List[float]],
        payloads: List[Dict[str, Any]]
    ) -> None:
        """插入或更新文档"""
        points = [
            PointStruct(
                id=self._string_to_int_id(doc_id),
                vector=vector,
                payload={**payload, "doc_id": doc_id}
            )
            for doc_id, vector, payload in zip(ids, vectors, payloads)
        ]
        
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            self.client.upsert(
                collection_name=self.collection_name,
                points=batch
            )
    
    def search(
        self,
        vector: List[float],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """向量搜索 (使用新版 query_points API)"""
        query_filter = None
        if filters:
            must_conditions = []
            for key, value in filters.items():
                must_conditions.append(
                    models.FieldCondition(
                        key=key,
                        match=models.MatchValue(value=value)
                    )
                )
            query_filter = models.Filter(must=must_conditions)
        
        # 使用新版 query_points API
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=vector,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True
        )
        
        return [
            {
                "id": point.payload.get("doc_id", str(point.id)),
                "content": point.payload.get("content", ""),
                "metadata": {
                    k: v for k, v in point.payload.items() 
                    if k not in ["content", "doc_id"]
                },
                "score": point.score
            }
            for point in results.points
        ]
    
    def get_collection_info(self) -> Dict[str, Any]:
        """获取集合信息"""
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                "name": self.collection_name,
                "vectors_count": info.indexed_vectors_count or 0,
                "points_count": info.points_count or 0,
                "status": info.status.value if info.status else "unknown"
            }
        except Exception as e:
            return {
                "name": self.collection_name, 
                "vectors_count": 0,
                "points_count": 0,
                "error": str(e)
            }


vectordb_service = VectorDBService()
