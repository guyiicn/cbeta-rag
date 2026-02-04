import httpx
import json
from typing import List, Dict, Any, AsyncGenerator, Optional
from dataclasses import dataclass, field

from app.core.config import settings, PRESET_PROVIDERS


class ProviderNotFoundError(Exception):
    """Provider 不存在"""
    pass


class LLMServiceDegraded(Exception):
    """LLM 服务降级"""
    pass


@dataclass
class LLMConfig:
    """LLM 配置，支持预设或自定义"""
    provider: str = ""
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    # 降级标记
    is_fallback: bool = False
    original_provider: str = ""
    
    @classmethod
    def from_request(
        cls,
        provider: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ) -> "LLMConfig":
        """从请求参数构建配置"""
        config = cls()
        config.provider = provider or settings.DEFAULT_PROVIDER
        
        if base_url:
            config.base_url = base_url
            config.api_key = api_key or ""
            config.model = model or "custom-model"
            return config
        
        if config.provider not in PRESET_PROVIDERS:
            available = ", ".join(PRESET_PROVIDERS.keys())
            raise ProviderNotFoundError(f"Provider '{config.provider}' 不存在。可用: {available}")
        
        preset = PRESET_PROVIDERS[config.provider]
        config.base_url = preset.get("base_url", "")
        config.api_key = api_key or settings.get_api_key(config.provider)
        config.model = model or preset.get("default_model", "")
        
        return config
    
    def to_fallback(self) -> "LLMConfig":
        """创建 Ollama 降级配置"""
        fallback = LLMConfig()
        fallback.provider = "ollama"
        fallback.base_url = PRESET_PROVIDERS["ollama"]["base_url"]
        fallback.api_key = ""
        fallback.model = PRESET_PROVIDERS["ollama"]["default_model"]
        fallback.is_fallback = True
        fallback.original_provider = self.provider
        return fallback


# 触发降级的错误类型
FALLBACK_ERRORS = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
)

# 触发降级的 HTTP 状态码
FALLBACK_STATUS_CODES = {429, 500, 502, 503, 504}


class LLMService:
    def __init__(self):
        self.fallback_enabled = True  # 是否启用降级
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        config: Optional[LLMConfig] = None,
        stream: bool = False,
        allow_fallback: bool = True
    ) -> str | AsyncGenerator[str, None]:
        """调用 LLM，支持自动降级到 Ollama"""
        if config is None:
            config = LLMConfig.from_request()
        
        # 如果已经是 Ollama，直接调用不降级
        if config.provider == "ollama":
            return await self._call_llm(messages, config, stream)
        
        # 尝试调用远程 API
        try:
            return await self._call_llm(messages, config, stream)
        
        except FALLBACK_ERRORS as e:
            if allow_fallback and self.fallback_enabled:
                print(f"[降级] {config.provider} 连接失败 ({type(e).__name__})，切换到 Ollama")
                fallback_config = config.to_fallback()
                return await self._call_llm(messages, fallback_config, stream)
            raise
        
        except httpx.HTTPStatusError as e:
            if allow_fallback and self.fallback_enabled and e.response.status_code in FALLBACK_STATUS_CODES:
                print(f"[降级] {config.provider} 返回 {e.response.status_code}，切换到 Ollama")
                fallback_config = config.to_fallback()
                return await self._call_llm(messages, fallback_config, stream)
            raise
    
    async def _call_llm(
        self,
        messages: List[Dict[str, str]],
        config: LLMConfig,
        stream: bool
    ) -> str | AsyncGenerator[str, None]:
        """实际调用 LLM"""
        # Ollama
        if config.provider == "ollama" or "ollama" in config.base_url.lower():
            return await self._ollama_chat(messages, config, stream)
        
        # Anthropic
        if config.provider == "anthropic" or "anthropic" in config.base_url.lower():
            return await self._anthropic_chat(messages, config, stream)
        
        # OpenAI 兼容
        return await self._openai_chat(messages, config, stream)
    
    async def _openai_chat(
        self,
        messages: List[Dict[str, str]],
        config: LLMConfig,
        stream: bool
    ) -> str | AsyncGenerator[str, None]:
        """OpenAI 兼容 API"""
        if stream:
            return self._openai_stream(messages, config)
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            headers = {"Content-Type": "application/json"}
            if config.api_key:
                headers["Authorization"] = f"Bearer {config.api_key}"
            
            response = await client.post(
                f"{config.base_url}/chat/completions",
                headers=headers,
                json={"model": config.model, "messages": messages, "stream": False}
            )
            response.raise_for_status()
            data = response.json()
            
            content = data["choices"][0]["message"]["content"]
            
            # 如果是降级的响应，添加标记
            if config.is_fallback:
                content = f"[使用本地模型 {config.model} 回答，原服务 {config.original_provider} 暂时不可用]\n\n{content}"
            
            return content
    
    async def _openai_stream(
        self,
        messages: List[Dict[str, str]],
        config: LLMConfig
    ) -> AsyncGenerator[str, None]:
        """OpenAI 兼容流式"""
        # 如果是降级，先发送提示
        if config.is_fallback:
            yield f"[使用本地模型 {config.model}，原服务 {config.original_provider} 暂时不可用]\n\n"
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            headers = {"Content-Type": "application/json"}
            if config.api_key:
                headers["Authorization"] = f"Bearer {config.api_key}"
            
            async with client.stream(
                "POST",
                f"{config.base_url}/chat/completions",
                headers=headers,
                json={"model": config.model, "messages": messages, "stream": True}
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]
                        except json.JSONDecodeError:
                            continue
    
    async def _anthropic_chat(
        self,
        messages: List[Dict[str, str]],
        config: LLMConfig,
        stream: bool
    ) -> str | AsyncGenerator[str, None]:
        """Anthropic API"""
        system_content = ""
        chat_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
            else:
                chat_messages.append(msg)
        
        if stream:
            return self._anthropic_stream(chat_messages, system_content, config)
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            payload = {"model": config.model, "max_tokens": 4096, "messages": chat_messages}
            if system_content:
                payload["system"] = system_content
            
            response = await client.post(
                f"{config.base_url}/messages",
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": config.api_key,
                    "anthropic-version": "2023-06-01"
                },
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            
            content = data["content"][0]["text"]
            if config.is_fallback:
                content = f"[使用本地模型 {config.model}，原服务 {config.original_provider} 暂时不可用]\n\n{content}"
            
            return content
    
    async def _anthropic_stream(
        self,
        messages: List[Dict[str, str]],
        system_content: str,
        config: LLMConfig
    ) -> AsyncGenerator[str, None]:
        """Anthropic 流式"""
        if config.is_fallback:
            yield f"[使用本地模型 {config.model}，原服务 {config.original_provider} 暂时不可用]\n\n"
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            payload = {"model": config.model, "max_tokens": 4096, "messages": messages, "stream": True}
            if system_content:
                payload["system"] = system_content
            
            async with client.stream(
                "POST",
                f"{config.base_url}/messages",
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": config.api_key,
                    "anthropic-version": "2023-06-01"
                },
                json=payload
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            if data.get("type") == "content_block_delta":
                                delta = data.get("delta", {})
                                if "text" in delta:
                                    yield delta["text"]
                        except json.JSONDecodeError:
                            continue
    
    async def _ollama_chat(
        self,
        messages: List[Dict[str, str]],
        config: LLMConfig,
        stream: bool
    ) -> str | AsyncGenerator[str, None]:
        """本地 Ollama API"""
        if stream:
            return self._ollama_stream(messages, config)
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{config.base_url}/api/chat",
                json={"model": config.model, "messages": messages, "stream": False}
            )
            response.raise_for_status()
            
            content = response.json()["message"]["content"]
            if config.is_fallback:
                content = f"[使用本地模型 {config.model}，原服务 {config.original_provider} 暂时不可用]\n\n{content}"
            
            return content
    
    async def _ollama_stream(
        self,
        messages: List[Dict[str, str]],
        config: LLMConfig
    ) -> AsyncGenerator[str, None]:
        """Ollama 流式"""
        if config.is_fallback:
            yield f"[使用本地模型 {config.model}，原服务 {config.original_provider} 暂时不可用]\n\n"
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream(
                "POST",
                f"{config.base_url}/api/chat",
                json={"model": config.model, "messages": messages, "stream": True}
            ) as response:
                async for line in response.aiter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            if "message" in data and "content" in data["message"]:
                                yield data["message"]["content"]
                        except json.JSONDecodeError:
                            continue
    
    def list_providers(self) -> List[Dict[str, Any]]:
        """列出可用的 providers"""
        providers = []
        for name, preset in PRESET_PROVIDERS.items():
            api_key = settings.get_api_key(name)
            providers.append({
                "name": name,
                "base_url": preset["base_url"],
                "default_model": preset["default_model"],
                "configured": bool(api_key) or name == "ollama",
            })
        return providers


llm_service = LLMService()
