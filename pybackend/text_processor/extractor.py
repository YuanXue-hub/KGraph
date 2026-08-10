# text_processor/extractor.py

import re
from datetime import datetime
from typing import List, Dict
from .models import Article


class ArticleExtractor:
    """从文本中提取文章"""

    def __init__(self, text: str):
        self.text = text

    def extract(self) -> List[Article]:
        """
        按标题切分文章
        返回: List[Article]
        """
        if not self.text.strip():
            return []

        articles = []
        lines = self.text.split('\n')
        current = None
        content_lines = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if self._is_title(line):
                # 保存上一篇
                if current and content_lines:
                    current['content'] = '\n'.join(content_lines)
                    articles.append(Article(**current))

                # 开始新文章
                current = {
                    'title': line,
                    'date': self._extract_date(line),
                    'source': 'unknown',
                    'metadata': {}
                }
                content_lines = []
            elif current:
                content_lines.append(line)

        # 保存最后一篇
        if current and content_lines:
            current['content'] = '\n'.join(content_lines)
            articles.append(Article(**current))

        # 如果没有提取到标题，整个文本作为一篇
        if not articles and self.text.strip():
            articles.append(Article(
                title='全文',
                content=self.text,
                date=datetime.now().strftime('%Y-%m-%d'),
                source='unknown'
            ))

        return articles

    def _is_title(self, line: str) -> bool:
        """判断是否是标题"""
        if len(line) > 50:
            return False

        patterns = [
            r'^#{1,6}\s+',  # Markdown 标题
            r'^[一二三四五六七八九十]+[、.]',  # 中文数字
            r'^\d+[、.]',  # 阿拉伯数字
            r'^[A-Z][a-z]*\s+[A-Z]',  # 英文标题
        ]

        for pattern in patterns:
            if re.match(pattern, line):
                return True

        return False

    def _extract_date(self, text: str) -> str:
        """从文本中提取日期"""
        match = re.search(r'(\d{4}[-\/]\d{1,2}[-\/]\d{1,2})', text)
        if match:
            return match.group(1).replace('/', '-')
        return datetime.now().strftime('%Y-%m-%d')