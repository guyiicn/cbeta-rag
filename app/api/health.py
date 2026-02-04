from fastapi import APIRouter, Depends
from typing import Dict, Any
import httpx

from app.core.auth import verify_api_key
from app.core.config import settings, PRESET_PROVIDERS
from app.services.vectordb import vectordb_service

router = APIRouter()


@router.get("/health")
async def health() -> Dict[str, Any]:
    """健康检查 - 检查所有依赖服务"""
    status = {
        "status": "ok",
        "services": {},
        "fallback": {
            "enabled": True,
            "provider": "ollama",
            "model": PRESET_PROVIDERS["ollama"]["default_model"]
        }
    }
    all_healthy = True
    
    # 检查 Qdrant
    try:
        info = vectordb_service.get_collection_info()
        status["services"]["qdrant"] = {
            "status": "ok",
            "vectors_count": info.get("vectors_count", 0)
        }
    except Exception as e:
        status["services"]["qdrant"] = {"status": "error", "message": str(e)}
        all_healthy = False
    
    # 检查 Ollama (降级保证)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if response.status_code == 200:
                models = [m["name"] for m in response.json().get("models", [])]
                has_embedding = any("bge-m3" in m for m in models)
                has_llm = any("qwen" in m.lower() for m in models)
                status["services"]["ollama"] = {
                    "status": "ok",
                    "models_count": len(models),
                    "embedding_model": "ok" if has_embedding else "missing",
                    "fallback_llm": "ok" if has_llm else "missing"
                }
                status["fallback"]["available"] = has_llm
            else:
                status["services"]["ollama"] = {"status": "error", "message": f"HTTP {response.status_code}"}
                status["fallback"]["available"] = False
                all_healthy = False
    except Exception as e:
        status["services"]["ollama"] = {"status": "error", "message": str(e)}
        status["fallback"]["available"] = False
        all_healthy = False
    
    # 检查默认 LLM Provider
    default_provider = settings.DEFAULT_PROVIDER
    if default_provider != "ollama":
        try:
            preset = PRESET_PROVIDERS.get(default_provider, {})
            api_key = settings.get_api_key(default_provider)
            status["services"]["default_llm"] = {
                "provider": default_provider,
                "configured": bool(api_key),
                "base_url": preset.get("base_url", "")[:50] + "..."
            }
        except Exception as e:
            status["services"]["default_llm"] = {"status": "error", "message": str(e)}
    
    status["status"] = "ok" if all_healthy else "degraded"
    return status


@router.get("/v1/stats")
async def stats(api_key: str = Depends(verify_api_key)) -> Dict[str, Any]:
    """获取系统统计信息"""
    collection_info = vectordb_service.get_collection_info()
    
    # 获取所有配置的 providers
    configured_providers = []
    for name in PRESET_PROVIDERS.keys():
        if name == "ollama" or settings.get_api_key(name):
            configured_providers.append(name)
    
    return {
        "status": "ok",
        "collection": collection_info,
        "config": {
            "default_provider": settings.DEFAULT_PROVIDER,
            "rerank_top_k": settings.RERANK_TOP_K,
            "default_top_k": settings.DEFAULT_TOP_K,
            "configured_providers": configured_providers,
            "fallback_provider": "ollama"
        }
    }
