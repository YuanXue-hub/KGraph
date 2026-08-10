from .parser import FileParser
from typing import List
from pathlib import Path
from .extractor import ArticleExtractor
from .splitter import split_into_chunks, split_articles_into_chunks
from .models import Article, ProcessedDocument, DocumentMetadata


def process_file(file_path: str) -> ProcessedDocument:
    """
    处理单个文件：解析 → 提取文章
    """
    try:
        parser = FileParser(file_path)
        raw_text, metadata = parser.parse()

        extractor = ArticleExtractor(raw_text)
        articles = extractor.extract()

        return ProcessedDocument(
            success=True,
            file_name=metadata.file_name,
            file_type=metadata.file_type,
            raw_text=raw_text,
            articles=articles,
            metadata=metadata
        )
    except Exception as e:
        return ProcessedDocument(
            success=False,
            file_name=Path(file_path).name,
            file_type='unknown',
            raw_text='',
            articles=[],
            metadata=None,
            error=str(e)
        )


def process_directory(dir_path: str) -> List[ProcessedDocument]:
    """
    处理目录下所有支持的文件
    """
    path = Path(dir_path)
    results = []

    for ext in FileParser.SUPPORTED:
        for file_path in path.glob(f'*{ext}'):
            results.append(process_file(str(file_path)))

    return results