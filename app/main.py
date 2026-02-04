from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.api import search, chat, models, health
from app.services.vectordb import vectordb_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    print("CBETA RAG API 启动中...")
    
    # 确保集合存在
    try:
        vectordb_service.create_collection()
        print("Qdrant 集合已就绪")
    except Exception as e:
        print(f"Qdrant 连接警告: {e}")
    
    yield
    
    # 关闭时
    print("CBETA RAG API 关闭")


app = FastAPI(
    title="CBETA RAG API",
    description="佛经检索与问答系统 - OpenAI 兼容 API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(search.router, tags=["Search"])
app.include_router(chat.router, tags=["Chat"])
app.include_router(models.router, tags=["Models"])
app.include_router(health.router, tags=["Health"])


@app.get("/")
async def root():
    return {
        "name": "CBETA RAG API",
        "version": "1.0.0",
        "docs": "/docs"
    }
