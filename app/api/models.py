from fastapi import APIRouter, Depends
from typing import List, Dict, Any

from app.core.auth import verify_api_key
from app.services.llm import llm_service
from app.core.config import PRESET_PROVIDERS

router = APIRouter()


@router.get("/v1/models")
async def list_models(api_key: str = Depends(verify_api_key)):
    """列出可用模型 (OpenAI 兼容)"""
    models = []
    for provider, config in PRESET_PROVIDERS.items():
        models.append({
            "id": config["default_model"],
            "object": "model",
            "owned_by": provider,
        })
    return {"object": "list", "data": models}


@router.get("/v1/providers")
async def list_providers(api_key: str = Depends(verify_api_key)):
    """列出所有可用的 LLM providers 及其配置状态"""
    return {
        "providers": llm_service.list_providers(),
        "usage": {
            "预设 provider": {
                "description": "使用预设的 provider，API key 从环境变量读取",
                "example": {
                    "llm": {"provider": "deepseek"},
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": "你好"}]
                }
            },
            "覆盖 API key": {
                "description": "使用预设 provider，但覆盖 API key",
                "example": {
                    "llm": {"provider": "openai", "api_key": "sk-your-key"},
                    "model": "gpt-4o",
                    "messages": [{"role": "user", "content": "你好"}]
                }
            },
            "完全自定义": {
                "description": "完全自定义 base_url 和 api_key",
                "example": {
                    "llm": {
                        "base_url": "https://your-custom-api.com/v1",
                        "api_key": "your-api-key"
                    },
                    "model": "custom-model",
                    "messages": [{"role": "user", "content": "你好"}]
                }
            }
        }
    }
