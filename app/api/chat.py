import time
import uuid
import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from app.core.auth import verify_api_key
from app.core.rag import rag_pipeline
from app.services.llm import LLMConfig, ProviderNotFoundError

router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str


class LLMProviderConfig(BaseModel):
    """LLM 配置，支持动态切换 provider"""
    provider: Optional[str] = None       # 预设: qwen, glm, gemini, deepseek, openai, anthropic, ollama
    base_url: Optional[str] = None       # 自定义 API URL (覆盖预设)
    api_key: Optional[str] = None        # 自定义 API Key (覆盖环境变量)


class ChatRequest(BaseModel):
    model: Optional[str] = None          # 模型名称
    messages: List[ChatMessage]
    stream: bool = False
    rag: bool = True                     # 是否启用 RAG 检索
    llm: Optional[LLMProviderConfig] = None  # LLM provider 配置


class ChatChoice(BaseModel):
    index: int
    message: Dict[str, str]
    finish_reason: str


class ChatUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatChoice]
    usage: ChatUsage


@router.post("/v1/chat/completions")
async def chat_completions(
    request: ChatRequest,
    api_key: str = Depends(verify_api_key)
):
    """OpenAI 兼容的聊天补全 API
    
    支持动态切换 LLM provider:
    
    1. 使用预设 provider:
       {"llm": {"provider": "qwen"}, "model": "qwen-plus"}
       
    2. 完全自定义:
       {"llm": {"base_url": "https://custom.api/v1", "api_key": "sk-xxx"}}
       
    3. 覆盖预设的 API key:
       {"llm": {"provider": "openai", "api_key": "sk-my-key"}}
       
    可用 providers: qwen, glm, gemini, deepseek, openai, anthropic, openrouter, siliconflow, ollama
    """
    messages = [msg.model_dump() for msg in request.messages]
    
    try:
        # 构建 LLM 配置
        llm_config = LLMConfig.from_request(
            provider=request.llm.provider if request.llm else None,
            base_url=request.llm.base_url if request.llm else None,
            api_key=request.llm.api_key if request.llm else None,
            model=request.model
        )
        
        if request.stream:
            return StreamingResponse(
                stream_response(messages, llm_config, request.rag),
                media_type="text/event-stream"
            )
        
        # 非流式响应
        response_content = await rag_pipeline.ask(
            messages=messages,
            llm_config=llm_config,
            stream=False,
            rag=request.rag
        )
        
        return ChatCompletionResponse(
            id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
            created=int(time.time()),
            model=llm_config.model,
            choices=[
                ChatChoice(
                    index=0,
                    message={"role": "assistant", "content": response_content},
                    finish_reason="stop"
                )
            ],
            usage=ChatUsage()
        )
    
    except ProviderNotFoundError as e:
        return JSONResponse(
            status_code=400,
            content={"error": {"message": str(e), "type": "invalid_provider"}}
        )
    
    except Exception as e:
        error_msg = str(e)
        error_type = type(e).__name__
        provider = request.llm.provider if request.llm else "default"
        
        # 解析常见错误
        if "401" in error_msg or "Unauthorized" in error_msg or "身份验证失败" in error_msg:
            return JSONResponse(
                status_code=401,
                content={"error": {"message": f"API key 无效或已过期 ({provider})", "type": "authentication_error", "provider": provider}}
            )
        elif "429" in error_msg or "Too Many Requests" in error_msg or "rate limit" in error_msg.lower():
            return JSONResponse(
                status_code=429,
                content={"error": {"message": f"请求过于频繁，请稍后重试 ({provider})", "type": "rate_limit_error", "provider": provider}}
            )
        elif "ConnectError" in error_type or "timeout" in error_msg.lower() or "No address" in error_msg:
            return JSONResponse(
                status_code=503,
                content={"error": {"message": f"无法连接到 {provider} API，请检查网络", "type": "connection_error", "provider": provider}}
            )
        elif "404" in error_msg:
            return JSONResponse(
                status_code=404,
                content={"error": {"message": f"模型不存在或 API 端点错误", "type": "not_found", "provider": provider}}
            )
        else:
            # 通用错误
            return JSONResponse(
                status_code=500,
                content={"error": {"message": error_msg, "type": error_type, "provider": provider}}
            )


async def stream_response(messages: List[Dict], llm_config: LLMConfig, rag: bool):
    """生成 SSE 流式响应"""
    chat_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
    created = int(time.time())
    
    try:
        generator = await rag_pipeline.ask(
            messages=messages,
            llm_config=llm_config,
            stream=True,
            rag=rag
        )
        
        async for chunk in generator:
            data = {
                "id": chat_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": llm_config.model,
                "choices": [{
                    "index": 0,
                    "delta": {"content": chunk},
                    "finish_reason": None
                }]
            }
            yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
        
        # 发送结束标记
        final_data = {
            "id": chat_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": llm_config.model,
            "choices": [{
                "index": 0,
                "delta": {},
                "finish_reason": "stop"
            }]
        }
        yield f"data: {json.dumps(final_data)}\n\n"
        yield "data: [DONE]\n\n"
    
    except Exception as e:
        error_data = {
            "id": chat_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": llm_config.model,
            "choices": [{
                "index": 0,
                "delta": {"content": f"\n\n[错误: {str(e)}]"},
                "finish_reason": "error"
            }]
        }
        yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
