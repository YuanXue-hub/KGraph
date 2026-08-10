from pathlib import Path
from charset_normalizer import from_bytes
def detect_encoding(file_path: str) -> str:
    """
    检测文件编码，多级回退
    :param file_path:
    :return:
    """

    data = Path(file_path).read_bytes()
    try:
        data.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass

    try:
        best = from_bytes(data).best()
        if best and best.encoding:
            return best.encoding
    except ImportError:
        pass

    # 3. 尝试 chardet
    try:
        import chardet
        result = chardet.detect(data)
        if result and result.get('encoding'):
            return result['encoding']
    except ImportError:
        pass

    # 4. 兜底
    return 'utf-8'

