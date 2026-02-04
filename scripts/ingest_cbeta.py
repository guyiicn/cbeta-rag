#!/usr/bin/env python3
"""CBETA 批量导入脚本"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ingestion.cbeta_parser import load_cbeta_documents
from app.ingestion.chunker import ChineseTextChunker
from app.services.embedding import EmbeddingService
from app.services.vectordb import VectorDBService
from app.core.config import settings


async def main():
    print("=== CBETA RAG 导入脚本 ===")
    
    # 1. 初始化服务
    embedding_service = EmbeddingService()
    vectordb_service = VectorDBService()
    chunker = ChineseTextChunker(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP
    )
    
    # 2. 创建 collection
    print(f"创建集合: {settings.COLLECTION_NAME}")
    created = vectordb_service.create_collection()
    print(f"集合{'已创建' if created else '已存在'}")
    
    # 3. 遍历 CBETA 文档
    cbeta_path = settings.CBETA_DATA_PATH
    print(f"读取 CBETA 数据: {cbeta_path}")
    
    total_docs = 0
    total_chunks = 0
    
    batch_ids = []
    batch_vectors = []
    batch_payloads = []
    batch_size = 50
    
    for doc in load_cbeta_documents(cbeta_path):
        total_docs += 1
        
        # 4. 分块
        chunks = chunker.split(doc.content)
        
        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue
            
            chunk_id = f"{doc.id}_{i}"
            
            # 5. 生成 embedding
            try:
                embedding = await embedding_service.embed(chunk)
            except Exception as e:
                print(f"Embedding 失败 {chunk_id}: {e}")
                continue
            
            batch_ids.append(chunk_id)
            batch_vectors.append(embedding)
            batch_payloads.append({
                "content": chunk,
                "title": doc.title,
                "canon": doc.canon,
                "source": doc.source,
                "publish_date": doc.publish_date,
                "chunk_index": i
            })
            
            total_chunks += 1
            
            # 6. 批量存入 Qdrant
            if len(batch_ids) >= batch_size:
                vectordb_service.upsert_documents(
                    ids=batch_ids,
                    vectors=batch_vectors,
                    payloads=batch_payloads
                )
                print(f"已处理: {total_docs} 文档, {total_chunks} 块")
                batch_ids = []
                batch_vectors = []
                batch_payloads = []
    
    # 处理剩余的批次
    if batch_ids:
        vectordb_service.upsert_documents(
            ids=batch_ids,
            vectors=batch_vectors,
            payloads=batch_payloads
        )
    
    print(f"\n=== 导入完成 ===")
    print(f"总文档数: {total_docs}")
    print(f"总块数: {total_chunks}")
    
    # 7. 验证
    info = vectordb_service.get_collection_info()
    print(f"集合状态: {info}")


if __name__ == "__main__":
    asyncio.run(main())
