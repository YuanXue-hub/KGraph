from typing import List

def split_into_chunks(text: str, chunk_size: int=500, overlap: int=50) -> List[str]:
    """
    智能分块，在句子边界处切分
    """
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        if end < len(text):
            # 寻找句子的边界
            for sep in ['。', '！', '？', '.\n', '!\n', '?\n', '\n\n', '. ', '! ', '? ']:
                pos = text[start:end].rfind(sep)
                if pos != -1 and pos > chunk_size * 0.3:
                    end = start + pos + len(sep)
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        start = end - overlap if end < len(text) else len(text)
    return chunks


def split_articles_into_chunks(articles: List, chunk_size: int = 500) -> List[dict]:
    """
    将文章列表分块，保留标题信息
    """
    result = []
    for article in articles:
        chunks = split_into_chunks(article.content, chunk_size)
        for i, chunk in enumerate(chunks):
            result.append({
                'title': article.title,
                'chunk_index': i,
                'total_chunks': len(chunks),
                'content': chunk,
                'date': article.date,
                'source': article.source
            })
    return result