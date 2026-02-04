import os
import yaml
from dataclasses import dataclass
from typing import Generator, Optional
from pathlib import Path


@dataclass
class CBETADocument:
    id: str
    title: str
    content: str
    canon: str
    source: str
    publish_date: str
    contributors: str


def parse_yaml_metadata(yaml_path: str) -> dict:
    """解析 YAML 元数据文件"""
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        return {}


def parse_txt_content(txt_path: str) -> str:
    """解析 TXT 经文内容，跳过头部注释"""
    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 跳过以 # 开头的注释行
        content_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped.startswith('#'):
                content_lines.append(line)
        
        return ''.join(content_lines).strip()
    except Exception as e:
        return ""


def load_cbeta_documents(cbeta_path: str) -> Generator[CBETADocument, None, None]:
    """遍历 CBETA 目录，生成文档"""
    cbeta_root = Path(cbeta_path)
    
    if not cbeta_root.exists():
        print(f"CBETA path not found: {cbeta_path}")
        return
    
    # 遍历藏经目录 (T, X, J, etc.)
    for canon_dir in sorted(cbeta_root.iterdir()):
        if not canon_dir.is_dir():
            continue
        
        canon = canon_dir.name  # e.g., "T", "X"
        
        # 遍历每个经典目录
        for doc_dir in sorted(canon_dir.iterdir()):
            if not doc_dir.is_dir():
                continue
            
            doc_id = doc_dir.name  # e.g., "T0001", "T0251"
            
            # 查找 txt 和 yaml 文件
            txt_files = list(doc_dir.glob("*.txt"))
            yaml_files = list(doc_dir.glob("*.yaml"))
            
            if not txt_files:
                continue
            
            # 解析元数据
            metadata = {}
            if yaml_files:
                metadata = parse_yaml_metadata(str(yaml_files[0]))
            
            # 解析内容
            content = parse_txt_content(str(txt_files[0]))
            
            if not content:
                continue
            
            yield CBETADocument(
                id=doc_id,
                title=metadata.get("title", doc_id),
                content=content,
                canon=canon,
                source=metadata.get("source", ""),
                publish_date=metadata.get("publish_date", ""),
                contributors=metadata.get("contributors", "")
            )
