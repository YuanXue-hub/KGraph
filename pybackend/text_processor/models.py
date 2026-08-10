from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime


@dataclass
class DocumentMetadata:
    """文档元数据"""
    file_name: str
    file_type: str          # pdf, docx, txt, md
    file_size: int
    encoding: Optional[str] = None
    page_count: Optional[int] = None
    author: Optional[str] = None
    title: Optional[str] = None
    extracted_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Article:
    """一篇文章"""
    title: str
    content: str
    date: str
    source: str              # 来源标识（文件名或来源名）
    metadata: Dict = field(default_factory=dict)


@dataclass
class ProcessedDocument:
    """处理后的文档"""
    success: bool
    file_name: str
    file_type: str
    raw_text: str            # 原始文本
    articles: List[Article]  # 切分后的文章
    metadata: DocumentMetadata
    error: Optional[str] = None