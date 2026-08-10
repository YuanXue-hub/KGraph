from pathlib import Path
from typing import Optional
from .encoder import detect_encoding
from .models import DocumentMetadata

class FileParser:
    """文件解析器：PDF/TXT/MD/DOCX → 纯文本"""

    SUPPORTED = {'.pdf', '.txt', '.md', '.markdown', '.docx'}

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.path = Path(file_path)

    def parse(self) -> tuple[str, DocumentMetadata]:
        """
        返回: (文本内容, 元数据)
        """
        if not self.path.exists():
            raise FileNotFoundError(f"文件不存在: {self.file_path}")

        suffix = self.path.suffix.lower()
        if suffix not in self.SUPPORTED:
            raise ValueError(f"不支持的文件格式: {suffix}")

        metadata = DocumentMetadata(
            file_name=self.path.name,
            file_type=suffix[1:],  # 去掉点
            file_size=self.path.stat().st_size
        )

        if suffix == '.pdf':
            content, extra = self._parse_pdf()
            metadata.page_count = extra.get('page_count')
            metadata.author = extra.get('author')
            metadata.title = extra.get('title')
        elif suffix == '.docx':
            content = self._parse_docx()
        else:
            content = self._parse_text()
            metadata.encoding = detect_encoding(self.file_path)

        return content, metadata

    def _parse_pdf(self) -> tuple[str, dict]:
        try:
            import fitz
        except ImportError:
            raise ImportError("请安装 PyMuPDF: pip install PyMuPDF")

        doc = fitz.open(self.file_path)
        texts = []
        for page in doc:
            texts.append(page.get_text())

        metadata = {
            'page_count': len(doc),
            'author': doc.metadata.get('author', ''),
            'title': doc.metadata.get('title', '')
        }
        doc.close()

        return '\n\n'.join(texts), metadata

    def _parse_docx(self) -> str:
        try:
            from docx import Document
        except ImportError:
            raise ImportError("请安装 python-docx: pip install python-docx")

        doc = Document(self.file_path)
        return '\n'.join(p.text for p in doc.paragraphs if p.text.strip())

    def _parse_text(self) -> str:
        encoding = detect_encoding(self.file_path)
        return self.path.read_text(encoding=encoding)