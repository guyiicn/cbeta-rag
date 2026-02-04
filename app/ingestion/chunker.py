from typing import List
import re


class ChineseTextChunker:
    def __init__(self, chunk_size: int = 200, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = ["\n\n", "\n", "。", "！", "？", "；", "，"]
    
    def split(self, text: str) -> List[str]:
        """按中文标点分割文本"""
        if not text:
            return []
        
        # 递归分割
        chunks = self._split_recursive(text, self.separators)
        
        # 合并过小的块
        merged = self._merge_chunks(chunks)
        
        return merged
    
    def _split_recursive(self, text: str, separators: List[str]) -> List[str]:
        """递归按分隔符分割"""
        if not separators:
            # 没有更多分隔符，按字符数强制分割
            return self._split_by_size(text)
        
        sep = separators[0]
        remaining_seps = separators[1:]
        
        # 按当前分隔符分割
        if sep in text:
            parts = text.split(sep)
            chunks = []
            for i, part in enumerate(parts):
                if part:
                    # 保留分隔符（除了换行）
                    if sep not in ["\n", "\n\n"] and i < len(parts) - 1:
                        part = part + sep
                    
                    if len(part) <= self.chunk_size:
                        chunks.append(part)
                    else:
                        # 太长，继续用下一个分隔符分割
                        chunks.extend(self._split_recursive(part, remaining_seps))
            return chunks
        else:
            # 当前分隔符不存在，尝试下一个
            return self._split_recursive(text, remaining_seps)
    
    def _split_by_size(self, text: str) -> List[str]:
        """按大小分割"""
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            chunks.append(text[start:end])
            start = end - self.chunk_overlap if end < len(text) else end
        return chunks
    
    def _merge_chunks(self, chunks: List[str]) -> List[str]:
        """合并过小的块"""
        if not chunks:
            return []
        
        merged = []
        current = chunks[0]
        
        for chunk in chunks[1:]:
            if len(current) + len(chunk) <= self.chunk_size:
                current += chunk
            else:
                if current.strip():
                    merged.append(current.strip())
                current = chunk
        
        if current.strip():
            merged.append(current.strip())
        
        return merged
