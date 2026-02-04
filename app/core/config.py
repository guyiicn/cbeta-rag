from pydantic_settings import BaseSettings
from typing import List, Dict, Any, Optional


# 预设的 LLM Provider 配置
PRESET_PROVIDERS: Dict[str, Dict[str, str]] = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o",
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1",
        "default_model": "claude-sonnet-4-20250514",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
    },
    "glm": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-flash",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "default_model": "gemini-2.0-flash",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "anthropic/claude-sonnet-4",
    },
    "siliconflow": {
        "base_url": "https://api.siliconflow.cn/v1",
        "default_model": "Qwen/Qwen2.5-72B-Instruct",
    },
    "ollama": {
        "base_url": "http://host.docker.internal:11434",
        "default_model": "qwen3:8b",
    },
}


class Settings(BaseSettings):
    # API Authentication
    API_KEY: str = "changeme"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    # Default LLM Provider (when not specified in request)
    DEFAULT_PROVIDER: str = "ollama"
    
    # API Keys for each provider (set via env vars)
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""
    QWEN_API_KEY: str = ""           # 阿里云 DashScope API Key
    GLM_API_KEY: str = ""            # 智谱 GLM API Key
    GEMINI_API_KEY: str = ""         # Google AI Studio API Key
    OPENROUTER_API_KEY: str = ""
    SILICONFLOW_API_KEY: str = ""
    
    # Local Ollama (always available)
    OLLAMA_BASE_URL: str = "http://host.docker.internal:11434"
    LOCAL_LLM_MODEL: str = "qwen3:8b"
    
    # Embedding (always local Ollama)
    EMBEDDING_MODEL: str = "bge-m3:latest"
    RERANKER_MODEL: str = "linux6200/bge-reranker-v2-m3:latest"
    
    # Qdrant
    QDRANT_HOST: str = "qdrant"
    QDRANT_PORT: int = 6333
    COLLECTION_NAME: str = "cbeta"
    VECTOR_DIM: int = 1024
    
    # CBETA
    CBETA_DATA_PATH: str = "/data/cbeta/cbeta-text"
    
    # RAG
    DEFAULT_TOP_K: int = 10
    RERANK_TOP_K: int = 5
    CHUNK_SIZE: int = 200
    CHUNK_OVERLAP: int = 50

    def get_api_key(self, provider: str) -> str:
        """获取指定 provider 的 API key"""
        key_map = {
            "openai": self.OPENAI_API_KEY,
            "anthropic": self.ANTHROPIC_API_KEY,
            "deepseek": self.DEEPSEEK_API_KEY,
            "qwen": self.QWEN_API_KEY,
            "glm": self.GLM_API_KEY,
            "gemini": self.GEMINI_API_KEY,
            "openrouter": self.OPENROUTER_API_KEY,
            "siliconflow": self.SILICONFLOW_API_KEY,
            "ollama": "",
        }
        return key_map.get(provider, "")

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
