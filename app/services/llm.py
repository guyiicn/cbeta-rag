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


# 降级链配置：主 API -> deepseek -> ollama
FALLBACK_CHAIN = ["glm", "ollama"]


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
    fallback_level: int = 0  # 降级层级: 0=主, 1=deepseek, 2=ollama
    
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
    
    def to_fallback(self, level: int = 1) -> "LLMConfig":
        """创建降级配置
        level 1: deepseek
        level 2: ollama (本地)
        """
        if level >= len(FALLBACK_CHAIN):
            level = len(FALLBACK_CHAIN) - 1
        
        fallback_provider = FALLBACK_CHAIN[level]
        
        fallback = LLMConfig()
        fallback.provider = fallback_provider
        fallback.base_url = PRESET_PROVIDERS[fallback_provider]["base_url"]
        fallback.api_key = settings.get_api_key(fallback_provider)
        fallback.model = PRESET_PROVIDERS[fallback_provider]["default_model"]
        fallback.is_fallback = True
        fallback.original_provider = self.original_provider or self.provider
        fallback.fallback_level = level
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
        """调用 LLM，支持多级降级: 主 API -> deepseek -> ollama"""
        if config is None:
            config = LLMConfig.from_request()
        
        # 如果已经是 ollama（最后一级），直接调用不降级
        if config.provider == "ollama":
            return await self._call_llm(messages, config, stream)
        
        # 尝试调用当前配置的 API
        try:
            return await self._call_llm(messages, config, stream)
        
        except FALLBACK_ERRORS as e:
            if allow_fallback and self.fallback_enabled:
                return await self._try_fallback(
                    messages, config, stream, 
                    error_msg=f"连接失败 ({type(e).__name__})"
                )
            raise
        
        except httpx.HTTPStatusError as e:
            if allow_fallback and self.fallback_enabled and e.response.status_code in FALLBACK_STATUS_CODES:
                return await self._try_fallback(
                    messages, config, stream,
                    error_msg=f"返回 {e.response.status_code}"
                )
            raise
    
    async def _try_fallback(
        self,
        messages: List[Dict[str, str]],
        config: LLMConfig,
        stream: bool,
        error_msg: str
    ) -> str | AsyncGenerator[str, None]:
        """尝试降级调用"""
        next_level = config.fallback_level + 1
        
        # 尝试降级链中的每个 provider
        while next_level <= len(FALLBACK_CHAIN):
            fallback_config = config.to_fallback(level=next_level)
            fallback_name = fallback_config.provider
            
            print(f"[降级] {config.provider} {error_msg}，尝试 {fallback_name} (level {next_level})")
            
            try:
                return await self._call_llm(messages, fallback_config, stream)
            except (httpx.HTTPStatusError, *FALLBACK_ERRORS) as e:
                if isinstance(e, httpx.HTTPStatusError):
                    if e.response.status_code not in FALLBACK_STATUS_CODES:
                        raise
                    error_msg = f"返回 {e.response.status_code}"
                else:
                    error_msg = f"连接失败 ({type(e).__name__})"
                
                config = fallback_config
                next_level += 1
                
                # 如果是最后一级 (ollama)，直接抛出异常
                if config.provider == "ollama":
                    print(f"[降级失败] 所有服务均不可用")
                    raise
        
        raise LLMServiceDegraded("所有 LLM 服务均不可用")
    
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
                content = f"[使用本地模型 {config.model}，原服务 {config.original_provider} 暂时不可用]\n\n{content}"
            
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
