from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from app.core.auth import verify_api_key
from app.core.rag import rag_pipeline

router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    top_k: int = 10
    filters: Optional[Dict[str, Any]] = None
    rerank: bool = True


class SearchResultItem(BaseModel):
    id: str
    content: str
    metadata: Dict[str, Any]
    score: float


class SearchResponse(BaseModel):
    results: List[SearchResultItem]


@router.post("/v1/search", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    api_key: str = Depends(verify_api_key)
):
    """检索相关佛经内容"""
    results = await rag_pipeline.search(
        query=request.query,
        top_k=request.top_k,
        filters=request.filters,
        rerank=request.rerank
    )
    
    return SearchResponse(
        results=[
            SearchResultItem(
                id=r.get("id", ""),
                content=r.get("content", ""),
                metadata=r.get("metadata", {}),
                score=r.get("score", 0.0)
            )
            for r in results
        ]
    )
