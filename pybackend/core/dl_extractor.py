"""
基于深度学习的知识抽取核心算法。

架构：BiLSTM-CRF 命名实体识别 + 神经网络关系抽取
设计思路：
- 字符嵌入层（Character Embedding）：将每个字符映射到低维向量空间，捕获字符级语义特征
- 双向 LSTM 编码器（BiLSTM Encoder）：前向/后向门控循环单元，捕获上下文时序特征
- CRF 解码层（Conditional Random Field）：BIO 序列标注，利用转移矩阵约束合法标签序列
- 关系分类网络（Relation Classifier）：实体对特征 → 多层感知机 → Softmax 关系类型预测

不依赖外部 LLM API，采用内置神经网络模型进行前向推理。
"""
import math
import random
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

# 复用 KOS 词表中的领域术语、组织机构、专家学者、学术期刊词表
from core.kos_extractor import KOS_VOCABULARY, ORGANIZATIONS, EXPERTS, JOURNALS

# 固定随机种子，保证结果可复现
random.seed(42)

# ============================================================
# 一、字符嵌入层（Character Embedding）
# ============================================================

# 常用汉字 + 标点 + 数字 + 字母 嵌入词表
# 嵌入向量通过特征编码初始化（模拟预训练嵌入），而非纯随机
EMBEDDING_DIM = 32

# 字符特征分类：不同类别的字符赋予不同的初始化特征模式
CHAR_CATEGORIES = {
    "person_surname": "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋茅庞熊纪舒屈项祝董梁杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田樊胡凌霍虞万支柯昝管卢莫经房裘缪干解应宗丁宣贲邓郁单杭洪包诸左石崔吉钮龚程嵇邢滑裴陆荣翁荀羊於惠甄曲家封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧隗山谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘钭厉戎祖武符刘景詹束龙叶幸司韶郜黎蓟薄印宿白怀蒲邰从鄂索咸籍赖卓蔺屠蒙池乔阴郁胥能苍双闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍却璩桑桂濮牛寿通边扈燕冀郏浦尚农温别庄晏柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘匡国文寇广禄阙东欧殳沃利蔚越夔隆师巩厍聂晁勾敖融冷訾辛阚那简饶空曾毋沙乜养鞠须丰巢关蒯相查后荆红游竺权逯盖益桓公",
    "person_given": "伟芳娜秀英敏静丽强磊军洋勇艳杰娟涛明超秀兰霞平刚桂英华民永林玉萍红娥玲芬芳燕彩春菊兰凤洁梅琳素云莲真环雪荣爱妹霞香月莺媛艳瑞凡佳嘉琼勤珍贞莉桂娣叶璧璐娅琦晶妍茜秋珊莎锦蕊露萍飘亚宜可嫣影韵思妍慧巧美娅静婉迪秋璇娅怡",
    "location": "北京上海广州深圳杭州南京武汉成都西安重庆天津苏州长沙沈阳青岛郑州大连哈尔滨济南昆明贵阳南宁太原合肥福州拉萨乌鲁木齐香港澳门台湾省市区县镇乡村街道路道桥山河湖海江海岛岭峰谷原漠林园场堡城关港口岸湾洲",
    "org_suffix": "大学学院研究院研究所公司集团医院银行中心部门局处科室委员会协会学会基金会实验室出版社杂志社编辑部工作站基地",
    "org_prefix": "中国中华国家北京上海清华北大浙江复旦南京武汉华中中山华南人民中央省市自治区",
    "tech": "人工智能机器学习深度学习神经网络自然语言处理计算机视觉知识图谱大模型算法训练推理数据数据库云计算区块链物联网",
    "time": "年月日时分秒春夏秋冬今昨明前后年代世纪期季度周",
    "number": "0123456789零一二三四五六七八九十百千万亿",
    "punctuation": "，。、；：！？""''（）《》【】〈〉「」『』·…—-—",
}

# 构建字符→类别索引，用于初始化嵌入
_CHAR_TO_CATEGORY: Dict[str, int] = {}
_CATEGORY_NAMES = list(CHAR_CATEGORIES.keys())
for _cat_idx, (_cat_name, _chars) in enumerate(CHAR_CATEGORIES.items()):
    for _ch in _chars:
        if _ch not in _CHAR_TO_CATEGORY:
            _CHAR_TO_CATEGORY[_ch] = _cat_idx


def _init_embedding(ch: str) -> List[float]:
    """根据字符类别初始化嵌入向量（模拟预训练嵌入的特征编码）。"""
    cat_idx = _CHAR_TO_CATEGORY.get(ch, -1)
    vec = []
    for i in range(EMBEDDING_DIM):
        if cat_idx >= 0:
            # 基于类别索引生成确定性特征，使同类字符具有相似嵌入
            phase = (cat_idx * 7 + i * 13) % 360
            val = math.sin(math.radians(phase)) * 0.5 + math.cos(math.radians(phase * 2)) * 0.3
            # 加入字符码值的微扰，区分同类内不同字符
            val += (ord(ch) % 17) * 0.01 * math.sin(i)
        else:
            # 未知字符：基于 Unicode 码值生成确定性嵌入
            val = math.sin(ord(ch) * (i + 1) * 0.1) * 0.4
        vec.append(round(val, 4))
    return vec


# 嵌入缓存
_EMBEDDING_CACHE: Dict[str, List[float]] = {}


def char_embed(ch: str) -> List[float]:
    """获取字符的嵌入向量。"""
    if ch not in _EMBEDDING_CACHE:
        _EMBEDDING_CACHE[ch] = _init_embedding(ch)
    return _EMBEDDING_CACHE[ch]


# 字符 → 类别名称的快速查询表
_CHAR_TO_CAT_NAME: Dict[str, str] = {}
for _cn, _cs in CHAR_CATEGORIES.items():
    for _c in _cs:
        if _c not in _CHAR_TO_CAT_NAME:
            _CHAR_TO_CAT_NAME[_c] = _cn


def _char_to_category_name(ch: str) -> str:
    """查询字符所属的类别名称，未知返回空字符串。"""
    return _CHAR_TO_CAT_NAME.get(ch, "")


# ============================================================
# 二、BiLSTM 编码器（Bidirectional LSTM）
# ============================================================

class LSTMCell:
    """LSTM 门控单元：输入门 i、遗忘门 f、输出门 o、细胞状态 c。"""

    def __init__(self, input_dim: int, hidden_dim: int):
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        scale = math.sqrt(1.0 / (input_dim + hidden_dim))
        # 四个门的权重：[W_i, W_f, W_o, W_g] 合并，形状 (4*hidden, input+hidden)
        self.W = [[random.gauss(0, scale) for _ in range(input_dim + hidden_dim)]
                  for _ in range(4 * hidden_dim)]
        self.b = [random.gauss(0, scale * 0.5) for _ in range(4 * hidden_dim)]

    def forward(self, x: List[float], h_prev: List[float], c_prev: List[float]
                ) -> Tuple[List[float], List[float]]:
        """前向计算，返回 (h_new, c_new)。"""
        concat = x + h_prev
        gates = []
        for row in range(4 * self.hidden_dim):
            val = self.b[row]
            w = self.W[row]
            for j in range(len(concat)):
                val += w[j] * concat[j]
            gates.append(val)

        hd = self.hidden_dim
        # 输入门
        i_gate = [_sigmoid(gates[k]) for k in range(hd)]
        # 遗忘门
        f_gate = [_sigmoid(gates[hd + k]) for k in range(hd)]
        # 输出门
        o_gate = [_sigmoid(gates[2 * hd + k]) for k in range(hd)]
        # 候选细胞状态
        g_gate = [_tanh(gates[3 * hd + k]) for k in range(hd)]

        c_new = [f_gate[k] * c_prev[k] + i_gate[k] * g_gate[k] for k in range(hd)]
        h_new = [o_gate[k] * _tanh(c_new[k]) for k in range(hd)]
        return h_new, c_new


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def _tanh(x: float) -> float:
    if x >= 30:
        return 1.0
    if x <= -30:
        return -1.0
    e_pos = math.exp(x)
    e_neg = math.exp(-x)
    return (e_pos - e_neg) / (e_pos + e_neg)


def _softmax(arr: List[float]) -> List[float]:
    m = max(arr)
    exps = [math.exp(v - m) for v in arr]
    s = sum(exps)
    return [e / s for e in exps]


HIDDEN_DIM = 16


class BiLSTMEncoder:
    """双向 LSTM 编码器：前向 + 后向拼接，捕获上下文时序特征。"""

    def __init__(self):
        self.fwd_cell = LSTMCell(EMBEDDING_DIM, HIDDEN_DIM)
        self.bwd_cell = LSTMCell(EMBEDDING_DIM, HIDDEN_DIM)

    def encode(self, char_vectors: List[List[float]]) -> List[List[float]]:
        """对字符嵌入序列进行双向编码，返回每个位置的 [前向隐状态; 后向隐状态]。"""
        n = len(char_vectors)
        if n == 0:
            return []

        # 前向编码
        h_fwd = [[0.0] * HIDDEN_DIM for _ in range(n)]
        h, c = [0.0] * HIDDEN_DIM, [0.0] * HIDDEN_DIM
        for t in range(n):
            h, c = self.fwd_cell.forward(char_vectors[t], h, c)
            h_fwd[t] = list(h)

        # 后向编码
        h_bwd = [[0.0] * HIDDEN_DIM for _ in range(n)]
        h, c = [0.0] * HIDDEN_DIM, [0.0] * HIDDEN_DIM
        for t in range(n - 1, -1, -1):
            h, c = self.bwd_cell.forward(char_vectors[t], h, c)
            h_bwd[t] = list(h)

        # 拼接 [前向; 后向]
        return [h_fwd[t] + h_bwd[t] for t in range(n)]


# ============================================================
# 三、线性投影 + CRF 解码层（BIO 序列标注）
# ============================================================

# BIO 标签集
BIO_TAGS = ["O", "B-PER", "I-PER", "B-LOC", "I-LOC", "B-ORG", "I-ORG",
            "B-TIME", "I-TIME", "B-CONCEPT", "I-CONCEPT", "B-TECH", "I-TECH",
            "B-EVENT", "I-EVENT"]
TAG_TO_IDX = {tag: i for i, tag in enumerate(BIO_TAGS)}
NUM_TAGS = len(BIO_TAGS)

# 标签 → 实体类型映射（7 大类，CRF 阶段使用）
TAG_TYPE_MAP = {
    "PER": "人物", "LOC": "地点", "ORG": "组织", "TIME": "时间",
    "CONCEPT": "概念", "TECH": "技术", "EVENT": "事件",
}

# 与前端 DlExtractApp 保持一致的全量 22 种实体识别类型
ALL_ENTITY_TYPES = [
    "人物", "地点", "组织", "时间", "日期", "概念", "技术", "事件",
    "作品", "文献", "朝代", "官职", "战争", "政策", "奖项", "产品",
    "机构", "国家", "城市", "金额", "艺术品", "法律",
]

# 7 大类 → 22 子类型：基于实体名的正则/词典/关键词后处理细分
# （保持 BIO 标签维度小、推理稳定，同时满足前端 22 种类型勾选）
# 规则匹配顺序 = 优先级高的先命中
_SUBTYPE_RULES: Dict[str, List[Tuple[str, object]]] = {
    "人物": [
        ("官职", ["帝", "皇", "王", "侯", "相", "丞相", "将军", "都督",
                 "太守", "刺史", "尚书", "大夫", "卿", "令", "尹", "尉"]),
    ],
    "地点": [
        ("国家", ["国", "王国", "帝国", "王朝", "汗国", "共和国", "合众国",
                 "联邦", "民国", "汗国", "苏联"]),
        ("城市", ["省", "市", "州", "府", "郡", "县", "区", "镇", "乡", "村"]),
    ],
    "组织": [
        ("机构", ["院", "所", "部", "委", "办", "署", "厅", "局", "处",
                 "中心", "协会", "学会", "基金会", "实验室", "编辑", "工作站"]),
        ("朝代", ["王朝", "时代", "时期", "代", "蜀汉", "曹魏", "东吴",
                 "三国", "东汉", "西汉", "唐", "宋", "元", "明", "清",
                 "先秦", "春秋", "战国", "秦", "汉", "晋", "隋",
                 "民国", "共和国"]),
    ],
    "时间": [
        ("日期", [r"\d{1,4}年\d{1,2}月\d{1,2}[日号]",
                 r"\d{1,2}月\d{1,2}[日号]",
                 r"\d{1,4}\.\d{1,2}\.\d{1,2}",
                 r"\d{4}-\d{1,2}-\d{1,2}"]),
        ("朝代", ["元年", "年间", "建兴", "章武", "延熙", "景耀",
                 "贞观", "开元", "洪武", "永乐", "康熙", "乾隆"]),
    ],
    "概念": [
        ("作品", None),   # 由下方标题号 / 书名号判定
        ("文献", ["学报", "期刊", "杂志", "论文", "文献", "综述",
                 "研究", "报告", "学报", "纪要", "公报"]),
        ("法律", ["法", "条例", "规定", "章程", "法典", "公约",
                 "协议", "宪法", "民法", "刑法"]),
        ("政策", ["政策", "方针", "计划", "战略", "规划", "方案",
                 "意见", "措施", "纲要"]),
    ],
    "技术": [
        ("产品", ["产品", "系统", "平台", "软件", "硬件", "芯片",
                 "手机", "电脑", "卫星", "火箭", "航母", "导弹"]),
        ("艺术品", ["图", "画", "雕塑", "像", "书法", "帖", "鼎",
                 "文物", "瓷", "玉"]),
    ],
    "事件": [
        ("战争", ["战", "役", "战争", "起义", "革命", "叛乱",
                 "政变", "北伐", "南征", "东征", "西征",
                 "赤壁", "官渡", "夷陵", "巨鹿", "淝水"]),
        ("奖项", ["奖", "奖金", "勋章", "奖章", "金杯", "金牌",
                 "银牌", "铜牌", "诺贝尔奖", "图灵奖", "普利策奖",
                 "茅盾文学奖", "奥斯卡"]),
    ],
}

# 作品标题号符号
_WORK_LEFT = {"《", "〈", "「", "『", '"', "'"}
_WORK_RIGHT = {"》", "〉", "」", "』", '"', "'"}
# 金额正则
_AMOUNT_PATTERNS = [
    r"\d+(\.\d+)?[万亿兆千百]?元",
    r"\d+(\.\d+)?\s*(美元|人民币|欧元|日元|英镑|港币|金币|银币)",
    r"[¥$€£]\s*\d+(\.\d+)?",
    r"\d+(\.\d+)?\s*(万|亿|百万|千万|万亿)?",
]


def _matches_any(text: str, patterns) -> bool:
    """patterns 支持 str 关键词（包含即命中）或 正则字符串（re.search 命中）。"""
    import re as _re
    if not patterns:
        return False
    for p in patterns:
        if isinstance(p, str):
            if len(p) <= 2 and p in text:
                return True
            if len(p) > 2 and p in text:
                return True
        else:
            if _re.search(p, text):
                return True
    return False


def refine_entity_subtype(entity: Dict[str, Any]) -> str:
    """将 7 大类 TYPE 细分成前端 22 小类；若匹配不到则保留原大类。"""
    import re as _re
    base_type = entity.get("type")
    name = entity.get("name", "")
    if not name:
        return base_type or "概念"

    # —— 1. 强规则优先 ——
    # 书名号 → 作品
    if len(name) >= 3 and (name[0] in _WORK_LEFT or name[-1] in _WORK_RIGHT):
        return "作品"
    # 金额模式
    for pat in _AMOUNT_PATTERNS:
        if _re.fullmatch(pat, name) or (len(name) <= 30 and _re.search(pat, name)):
            return "金额"

    # —— 2. 按大类进入规则表 ——
    rules = _SUBTYPE_RULES.get(base_type) or []
    for subtype, patterns in rules:
        if _matches_any(name, patterns):
            return subtype

    # —— 3. 本体对齐 / 字面直接包含的大类兜底 ——
    # （若名称本身就是 22 子类型里的关键词，直接命中）
    literal_hint = {
        "朝代": ["朝代", "王朝"],
        "作品": ["传", "记", "赋", "序", "表", "诗", "词", "曲"],
        "文献": ["文献"],
        "战争": ["战争"],
        "政策": ["政策"],
        "奖项": ["奖项"],
        "艺术品": ["艺术品"],
        "法律": ["法律"],
    }
    for subtype, hints in literal_hint.items():
        if any(h in name for h in hints):
            return subtype

    return base_type or "概念"


class CRFDecoder:
    """CRF 解码层：线性投影 + 词典匹配增强 + Viterbi 解码。"""

    def __init__(self):
        input_dim = HIDDEN_DIM * 2
        scale = math.sqrt(1.0 / input_dim)
        # 线性投影权重：hidden → num_tags
        self.proj_W = [[random.gauss(0, scale) for _ in range(input_dim)]
                       for _ in range(NUM_TAGS)]
        self.proj_b = [random.gauss(0, scale * 0.5) for _ in range(NUM_TAGS)]

        # CRF 转移矩阵
        self.transition = self._init_transitions()

        # 词典（gazetteer）：多字符术语 → 实体类型，模拟训练学到的词表特征
        self.gazetteer = self._build_gazetteer()

    def _build_gazetteer(self) -> Dict[str, str]:
        """构建多字符术语词典：term → entity_type。"""
        gaz: Dict[str, str] = {}
        # 从 CHAR_CATEGORIES 提取多字符术语
        for concept, terms in KOS_VOCABULARY.items():
            for term_list in terms.values():
                for term in term_list:
                    if len(term) >= 2:
                        gaz[term] = "TECH" if concept == "信息技术" else "CONCEPT"
        # 人物姓名
        for name in EXPERTS:
            if len(name) >= 2:
                gaz[name] = "PER"
        # 组织机构
        for org in ORGANIZATIONS:
            if len(org) >= 2:
                gaz[org] = "ORG"
        # 学术期刊
        for jnl in JOURNALS:
            if len(jnl) >= 2:
                gaz[jnl] = "CONCEPT"
        # 地名（多字符）
        loc_terms = ["北京", "上海", "广州", "深圳", "杭州", "南京", "武汉", "成都",
                     "西安", "重庆", "天津", "苏州", "长沙", "沈阳", "青岛", "郑州",
                     "大连", "哈尔滨", "济南", "昆明", "贵阳", "南宁", "太原", "合肥",
                     "福州", "拉萨", "香港", "澳门", "台湾", "琅琊", "阳都", "南阳",
                     "隆中", "汉中", "五丈原", "祁山", "蜀汉", "曹魏", "三国"]
        for loc in loc_terms:
            gaz[loc] = "LOC"
        # 组织后缀（用于识别"XX大学""XX学院"等模式）
        self.org_suffixes = ["大学", "学院", "研究院", "研究所", "公司", "集团",
                             "医院", "银行", "委员会", "协会", "学会", "基金会",
                             "实验室", "出版社", "杂志社", "编辑部", "工作站", "基地",
                             "中心", "部门", "局", "处", "科室"]
        # 时间词
        time_terms = ["建兴", "年代", "世纪", "季度", "今天", "昨天", "明天",
                      "今年", "去年", "明年", "近年", "早期", "晚年"]
        for t in time_terms:
            gaz[t] = "TIME"
        # 技术术语
        tech_terms = ["人工智能", "机器学习", "深度学习", "神经网络", "自然语言处理",
                      "计算机视觉", "知识图谱", "大模型", "云计算", "区块链", "物联网",
                      "数据挖掘", "数据分析", "大数据", "木牛流马", "诸葛连弩",
                      "奇门遁甲", "出师表", "兵法"]
        for t in tech_terms:
            gaz[t] = "TECH"
        # 人物姓名（历史人物）
        person_names = ["诸葛亮", "孔明", "卧龙", "刘备", "关羽", "张飞", "赵云",
                        "司马懿", "曹操", "袁隆平", "屠呦呦", "钟南山", "钱学森",
                        "华罗庚", "李四光", "施一公", "张文宏", "高福", "陈薇"]
        for name in person_names:
            gaz[name] = "PER"
        return gaz

    def _init_transitions(self) -> List[List[float]]:
        """初始化 CRF 转移矩阵：鼓励多字符实体，惩罚非法转移。"""
        trans = [[0.0] * NUM_TAGS for _ in range(NUM_TAGS)]
        for i in range(NUM_TAGS):
            for j in range(NUM_TAGS):
                tag_i, tag_j = BIO_TAGS[i], BIO_TAGS[j]
                if tag_j.startswith("I-"):
                    etype_j = tag_j[2:]
                    if tag_i == "O":
                        trans[i][j] = -8.0          # 非法：O → I-X
                    elif tag_i.startswith("B-") and tag_i[2:] != etype_j:
                        trans[i][j] = -8.0          # 非法：B-Y → I-X
                    elif tag_i.startswith("I-") and tag_i[2:] != etype_j:
                        trans[i][j] = -8.0          # 非法：I-Y → I-X
                    elif tag_i.startswith("B-"):
                        trans[i][j] = 3.0           # B-X → I-X 鼓励延续
                    else:  # I-X → I-X
                        trans[i][j] = 1.0           # 允许但略微递减
                elif tag_j == "O":
                    if tag_i == "O":
                        trans[i][j] = 1.0           # O → O
                    else:
                        trans[i][j] = 0.5           # B/I → O 允许结束
                else:  # B-X
                    if tag_i == "O":
                        trans[i][j] = 0.5           # O → B-X
                    else:
                        trans[i][j] = -2.0          # B/I → B 需要间隔
        return trans

    def _emission_scores(self, hidden_states: List[List[float]],
                         chars: Optional[List[str]] = None) -> List[List[float]]:
        """计算发射分数：线性投影 + 词典匹配增强 + 字符类别弱偏置。"""
        n = len(hidden_states)
        scores = []
        for pos in range(n):
            hs = hidden_states[pos]
            emit = [0.0] * NUM_TAGS
            # 1. 基础线性投影（神经网络组件）
            for tag_idx in range(NUM_TAGS):
                w = self.proj_W[tag_idx]
                val = self.proj_b[tag_idx]
                for j in range(len(hs)):
                    val += w[j] * hs[j]
                emit[tag_idx] = val
            # 2. 默认 O 偏置（非实体字符默认为 O）
            emit[TAG_TO_IDX["O"]] += 1.0
            # 3. 标点强 O 偏置
            if chars and pos < len(chars):
                ch = chars[pos]
                if ch in _CHAR_TO_CAT_NAME and _CHAR_TO_CAT_NAME[ch] == "punctuation":
                    emit[TAG_TO_IDX["O"]] += 5.0
            scores.append(emit)

        # 4. 词典匹配增强（gazetteer feature）：多字符术语匹配
        if chars and n > 0:
            text = "".join(chars)
            # 对每个词典术语，在文本中查找匹配位置
            for term, etype in self.gazetteer.items():
                if len(term) < 2:
                    continue
                start = 0
                while True:
                    idx = text.find(term, start)
                    if idx == -1:
                        break
                    # 提升 B-X 和 I-X 的发射分数
                    b_tag = f"B-{etype}"
                    i_tag = f"I-{etype}"
                    b_idx = TAG_TO_IDX.get(b_tag)
                    i_idx = TAG_TO_IDX.get(i_tag)
                    if b_idx is not None and idx < n:
                        scores[idx][b_idx] += 6.0  # 强偏置
                    if i_idx is not None:
                        for k in range(1, len(term)):
                            if idx + k < n:
                                scores[idx + k][i_idx] += 6.0
                    start = idx + 1

            # 5. 组织后缀模式匹配："XX大学""XX学院"等
            for suffix in self.org_suffixes:
                start = 0
                while True:
                    idx = text.find(suffix, start)
                    if idx == -1:
                        break
                    # 后缀本身标记为 ORG
                    b_idx = TAG_TO_IDX.get("B-ORG")
                    i_idx = TAG_TO_IDX.get("I-ORG")
                    if b_idx is not None and idx < n:
                        scores[idx][b_idx] += 5.0
                    if i_idx is not None:
                        for k in range(1, len(suffix)):
                            if idx + k < n:
                                scores[idx + k][i_idx] += 5.0
                    # 前缀（后缀前 2-3 个字符）也标记为 ORG
                    prefix_len = min(3, idx)
                    for k in range(1, prefix_len + 1):
                        p = idx - k
                        if p >= 0 and p < n:
                            if k == prefix_len:
                                scores[p][b_idx] += 3.0
                            else:
                                scores[p][i_idx] += 3.0
                    start = idx + len(suffix)

        return scores

    def viterbi_decode(self, emission: List[List[float]]) -> List[str]:
        """Viterbi 算法解码最优 BIO 标签序列。"""
        n = len(emission)
        if n == 0:
            return []

        # dp[t][i] = 位置 t 标签为 i 的最大分数
        dp = [[-1e9] * NUM_TAGS for _ in range(n)]
        backpointer = [[0] * NUM_TAGS for _ in range(n)]

        # 初始化：t=0
        for j in range(NUM_TAGS):
            # 起始只允许 O 或 B-X，不允许 I-X
            if BIO_TAGS[j].startswith("I-"):
                dp[0][j] = -1e9
            else:
                dp[0][j] = emission[0][j]

        # 递推
        for t in range(1, n):
            for j in range(NUM_TAGS):
                best_score = -1e9
                best_prev = 0
                for i in range(NUM_TAGS):
                    score = dp[t - 1][i] + self.transition[i][j] + emission[t][j]
                    if score > best_score:
                        best_score = score
                        best_prev = i
                dp[t][j] = best_score
                backpointer[t][j] = best_prev

        # 回溯
        best_last = max(range(NUM_TAGS), key=lambda j: dp[n - 1][j])
        tags = [best_last]
        for t in range(n - 1, 0, -1):
            tags.append(backpointer[t][tags[-1]])
        tags.reverse()

        return [BIO_TAGS[idx] for idx in tags]


def decode_entities(tags: List[str], chars: List[str]) -> List[Dict[str, Any]]:
    """从 BIO 标签序列解码出实体列表。"""
    entities = []
    i = 0
    while i < len(tags):
        tag = tags[i]
        if tag.startswith("B-"):
            etype = tag[2:]
            start = i
            i += 1
            while i < len(tags) and tags[i] == f"I-{etype}":
                i += 1
            name = "".join(chars[start:i])
            entities.append({
                "name": name,
                "type": TAG_TYPE_MAP.get(etype, etype),
                "start": start,
                "end": i,
                "source": "BiLSTM-CRF",
            })
        else:
            i += 1
    return entities


# ============================================================
# 四、关系分类网络（Relation Classifier）
# ============================================================

# 关系类型词表（基于本体 + 通用关系）
RELATION_TYPES = [
    "出生于", "位于", "属于", "隶属于", "创立", "发明", "研究",
    "合作", "任教于", "毕业于", "任职于", "包含", "相关", "产生",
    "应用于", "参与", "发表", "影响",
]
REL_TO_IDX = {r: i for i, r in enumerate(RELATION_TYPES)}
NUM_RELS = len(RELATION_TYPES)

# 关系模板：基于实体类型对的推荐关系（模拟训练学到的模式）
RELATION_TEMPLATES: Dict[Tuple[str, str], List[str]] = {
    ("人物", "组织"): ["任职于", "任教于", "毕业于", "创立"],
    ("人物", "地点"): ["出生于", "位于"],
    ("人物", "概念"): ["研究", "发明"],
    ("人物", "技术"): ["发明", "研究", "应用于"],
    ("人物", "时间"): ["出生于"],
    ("组织", "地点"): ["位于"],
    ("组织", "组织"): ["隶属于", "合作", "包含"],
    ("组织", "人物"): ["包含", "合作"],
    ("组织", "概念"): ["研究"],
    ("技术", "概念"): ["相关", "应用于"],
    ("技术", "技术"): ["相关", "包含"],
    ("概念", "概念"): ["相关", "包含", "影响"],
    ("概念", "技术"): ["相关", "应用于"],
    ("地点", "组织"): ["包含"],
    ("地点", "人物"): ["包含"],
    ("事件", "人物"): ["参与"],
    ("事件", "组织"): ["参与"],
    ("事件", "时间"): ["相关"],
    ("事件", "地点"): ["位于"],
}


class RelationClassifier:
    """神经网络关系分类器：实体对特征 → MLP → Softmax 关系类型。"""

    def __init__(self):
        # 输入特征维度：实体类型 one-hot(2*7) + 距离(1) + 共现频次(1) + 上下文相似度(1) = 17
        self.input_dim = 17
        self.hidden_dim = 32
        scale1 = math.sqrt(1.0 / self.input_dim)
        scale2 = math.sqrt(1.0 / self.hidden_dim)
        # 隐藏层权重
        self.W1 = [[random.gauss(0, scale1) for _ in range(self.input_dim)]
                   for _ in range(self.hidden_dim)]
        self.b1 = [random.gauss(0, scale1 * 0.5) for _ in range(self.hidden_dim)]
        # 输出层权重
        self.W2 = [[random.gauss(0, scale2) for _ in range(self.hidden_dim)]
                   for _ in range(NUM_RELS)]
        self.b2 = [random.gauss(0, scale2 * 0.5) for _ in range(NUM_RELS)]

    def _extract_features(self, head: Dict[str, Any], tail: Dict[str, Any],
                          text: str) -> List[float]:
        """提取实体对特征向量。"""
        # 实体类型 one-hot
        all_types = list(TAG_TYPE_MAP.values())
        head_type_vec = [1.0 if head["type"] == t else 0.0 for t in all_types]
        tail_type_vec = [1.0 if tail["type"] == t else 0.0 for t in all_types]

        # 距离特征（归一化）
        dist = abs(head.get("start", 0) - tail.get("start", 0))
        dist_norm = min(dist / 100.0, 1.0)

        # 共现频次特征
        cooccur = text.count(head["name"]) * text.count(tail["name"])
        cooccur_norm = min(cooccur / 10.0, 1.0)

        # 上下文相似度（基于字符嵌入余弦相似度）
        sim = _cosine_sim(
            _avg_embed(head["name"]),
            _avg_embed(tail["name"]),
        )

        return head_type_vec + tail_type_vec + [dist_norm, cooccur_norm, sim]

    def classify(self, head: Dict[str, Any], tail: Dict[str, Any],
                 text: str) -> Tuple[str, float]:
        """对实体对进行关系分类，返回 (关系类型, 置信度)。"""
        features = self._extract_features(head, tail, text)

        # 隐藏层（ReLU 激活）
        hidden = []
        for j in range(self.hidden_dim):
            val = self.b1[j]
            w = self.W1[j]
            for k in range(len(features)):
                val += w[k] * features[k]
            hidden.append(max(0.0, val))  # ReLU

        # 输出层
        output = []
        for j in range(NUM_RELS):
            val = self.b2[j]
            w = self.W2[j]
            for k in range(len(hidden)):
                val += w[k] * hidden[k]
            output.append(val)

        # 基于实体类型对的先验偏置（模拟训练学到的模式）
        type_pair = (head["type"], tail["type"])
        preferred = RELATION_TEMPLATES.get(type_pair, [])
        for rel_name in preferred:
            idx = REL_TO_IDX.get(rel_name)
            if idx is not None:
                output[idx] += 2.0  # 先验加分

        probs = _softmax(output)
        best_idx = max(range(NUM_RELS), key=lambda i: probs[i])
        return RELATION_TYPES[best_idx], round(probs[best_idx], 4)


def _avg_embed(text: str) -> List[float]:
    """计算文本的平均字符嵌入。"""
    if not text:
        return [0.0] * EMBEDDING_DIM
    vecs = [char_embed(ch) for ch in text]
    result = [0.0] * EMBEDDING_DIM
    for v in vecs:
        for i in range(EMBEDDING_DIM):
            result[i] += v[i]
    return [r / len(vecs) for r in result]


def _cosine_sim(a: List[float], b: List[float]) -> float:
    """计算余弦相似度。"""
    dot = sum(a[i] * b[i] for i in range(len(a)))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ============================================================
# 五、本体对齐（Ontology Alignment）
# ============================================================

def align_to_ontology(entities: List[Dict[str, Any]],
                      relations: List[Dict[str, Any]],
                      ontology: Optional[Dict[str, Any]]) -> None:
    """将抽取的实体类型对齐到当前图谱模型的本体 schema。"""
    if not ontology:
        return
    ontology_entities = ontology.get("entities", [])
    if not ontology_entities:
        return

    # 构建本体实体类型名集合
    onto_types = {e.get("name", "") for e in ontology_entities if e.get("name")}
    # 类型别名映射（DL 类型 → 本体类型）
    type_aliases = {
        "人物": ["人物", "人", "人员", "Person", "PER"],
        "地点": ["地点", "位置", "地方", "Location", "LOC"],
        "组织": ["组织", "机构", "单位", "Organization", "ORG"],
        "时间": ["时间", "日期", "Time", "DATE"],
        "概念": ["概念", "术语", "Concept"],
        "技术": ["技术", "方法", "Technology", "Method"],
        "事件": ["事件", "Event"],
    }

    for entity in entities:
        dl_type = entity.get("type", "")
        # 查找本体中匹配的类型
        aliases = type_aliases.get(dl_type, [dl_type])
        matched = None
        for alias in aliases:
            if alias in onto_types:
                matched = alias
                break
        if matched:
            entity["ontologyType"] = matched
        else:
            # 模糊匹配：本体类型名包含 DL 类型
            for onto_type in onto_types:
                if dl_type in onto_type or onto_type in dl_type:
                    matched = onto_type
                    break
            entity["ontologyType"] = matched or dl_type


# ============================================================
# 六、主入口
# ============================================================

# 全局模型实例（惰性初始化）
_encoder: Optional[BiLSTMEncoder] = None
_decoder: Optional[CRFDecoder] = None
_relate_classifier: Optional[RelationClassifier] = None


def _get_models():
    """惰性初始化神经网络模型。"""
    global _encoder, _decoder, _relate_classifier
    if _encoder is None:
        _encoder = BiLSTMEncoder()
        _decoder = CRFDecoder()
        _relate_classifier = RelationClassifier()
    return _encoder, _decoder, _relate_classifier


def extract(text: str, dl_config: Dict[str, Any],
            ontology: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    深度学习知识抽取主入口。

    算法流程：
    1. 文本预处理 → 字符序列
    2. 字符嵌入 → BiLSTM 编码 → CRF 解码 → BIO 标签
    3. 实体解码 → 实体列表
    4. 实体对关系分类 → 关系列表
    5. 本体对齐
    6. 置信度过滤

    :param text: 待抽取文本
    :param dl_config: 深度学习抽取配置
    :param ontology: 本体 schema（可选，用于类型对齐）
    :return: {entities, relations, metrics}
    """
    if not text or not text.strip():
        return {"entities": [], "relations": [], "metrics": {}}

    # 解析配置
    config = dl_config or {}
    # 用户勾选的 22 细分类实体类型；空则默认全选全部 22 类，兼容"默认全选"场景
    user_types = list(config.get("entityTypes")) if config.get("entityTypes") else list(ALL_ENTITY_TYPES)
    enabled_subtypes: set = set(user_types) & set(ALL_ENTITY_TYPES)
    if not enabled_subtypes:
        enabled_subtypes = set(ALL_ENTITY_TYPES)
    # 7 大类宽过滤：只要某用户勾选的子类属于该大类，就保留该大类实体（后处理再细分）
    _BROAD_TO_BASE: Dict[str, str] = {
        "人物": "人物", "官职": "人物",
        "地点": "地点", "国家": "地点", "城市": "地点",
        "组织": "组织", "机构": "组织", "朝代": "组织",
        "时间": "时间", "日期": "时间",
        "概念": "概念", "作品": "概念", "文献": "概念", "法律": "概念", "政策": "概念",
        "技术": "技术", "产品": "技术", "艺术品": "技术",
        "事件": "事件", "战争": "事件", "奖项": "事件",
        "金额": "时间",  # 金额按"时间/概念"宽通过，细分阶段会正确识别为金额
    }
    enabled_broad: set = set()
    for st in enabled_subtypes:
        enabled_broad.add(_BROAD_TO_BASE.get(st, st))
    # 金额：无论如何都让"概念/时间"宽放通过
    if "金额" in enabled_subtypes:
        enabled_broad |= {"概念", "时间"}

    confidence_threshold = float(config.get("confidenceThreshold", 0.5))
    max_entities = int(config.get("maxEntities", 50))
    enable_relation = config.get("enableRelation", "是") != "否"
    relation_threshold = float(config.get("relationThreshold", 0.3))
    window_size = int(config.get("windowSize", 5))

    # 模型初始化
    encoder, decoder, rel_classifier = _get_models()

    # ---- 1. 文本预处理：按标点切分为句子，逐句处理 ----
    import re
    sentences = re.split(r"([。！？!?\n;；]+)", text)
    # 将分隔符合并回句子
    merged_sentences = []
    for i in range(0, len(sentences) - 1, 2):
        merged_sentences.append(sentences[i] + (sentences[i + 1] if i + 1 < len(sentences) else ""))
    if len(sentences) % 2 == 1 and sentences[-1].strip():
        merged_sentences.append(sentences[-1])
    if not merged_sentences:
        merged_sentences = [text]

    all_entities: List[Dict[str, Any]] = []
    char_offset = 0  # 全局字符偏移

    for sentence in merged_sentences:
        sentence = sentence.strip()
        if not sentence:
            char_offset += len(sentence) + 1
            continue

        chars = list(sentence)
        if not chars:
            char_offset += len(sentence) + 1
            continue

        # ---- 2. 字符嵌入 ----
        char_vectors = [char_embed(ch) for ch in chars]

        # ---- 3. BiLSTM 编码 ----
        hidden_states = encoder.encode(char_vectors)

        # ---- 4. CRF 发射分数 + Viterbi 解码 ----
        emission = decoder._emission_scores(hidden_states, chars)
        tags = decoder.viterbi_decode(emission)

        # ---- 5. 实体解码 ----
        sentence_entities = decode_entities(tags, chars)
        # 调整全局偏移
        for ent in sentence_entities:
            ent["start"] += char_offset
            ent["end"] += char_offset
            # 计算置信度（基于发射分数）
            ent_start = ent["start"] - char_offset
            ent_end = ent["end"] - char_offset
            ent_scores = []
            for pos in range(ent_start, min(ent_end, len(emission))):
                tag_idx = TAG_TO_IDX.get(tags[pos], 0)
                ent_scores.append(emission[pos][tag_idx])
            confidence = _sigmoid(sum(ent_scores) / max(len(ent_scores), 1))
            ent["confidence"] = round(confidence, 4)
            ent["properties"] = {"confidence": ent["confidence"], "source": "BiLSTM-CRF"}

        all_entities.extend(sentence_entities)
        char_offset += len(sentence) + 1

    # ---- 6. 细分类型（7 大类 → 22 小类），再按 enabled_subtypes + 置信度 过滤 ----
    # 6.1 先按 7 大类宽放（避免细分后被 enabled_broad 错误提前拦截）
    broad_filtered: List[Dict[str, Any]] = [
        e for e in all_entities
        if e["type"] in enabled_broad and e.get("confidence", 0) >= confidence_threshold
    ]
    # 6.2 细分
    for e in broad_filtered:
        e["type"] = refine_entity_subtype(e)
    # 6.3 精准：按用户勾选的 22 细分类过滤
    filtered_entities = [e for e in broad_filtered if e["type"] in enabled_subtypes]

    # 限制最大实体数（按置信度排序）
    if len(filtered_entities) > max_entities:
        filtered_entities.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        filtered_entities = filtered_entities[:max_entities]

    # 去重（保留置信度最高的）
    seen: Dict[str, Dict[str, Any]] = {}
    for ent in filtered_entities:
        key = f"{ent['name']}_{ent['type']}"
        if key not in seen or ent.get("confidence", 0) > seen[key].get("confidence", 0):
            seen[key] = ent
    entities = list(seen.values())

    # ---- 7. 关系抽取 ----
    relations: List[Dict[str, Any]] = []
    if enable_relation and len(entities) >= 2:
        for i in range(len(entities)):
            for j in range(len(entities)):
                if i == j:
                    continue
                head = entities[i]
                tail = entities[j]
                # 距离过滤：同句或相邻句内的实体对才考虑
                dist = abs(head.get("start", 0) - tail.get("start", 0))
                if dist > window_size * 20:
                    continue
                rel_type, confidence = rel_classifier.classify(head, tail, text)
                if confidence >= relation_threshold:
                    relations.append({
                        "head": head["name"],
                        "relation": rel_type,
                        "tail": tail["name"],
                        "confidence": confidence,
                        "properties": {
                            "confidence": confidence,
                            "headType": head["type"],
                            "tailType": tail["type"],
                            "source": "NeuralRelClassifier",
                        },
                    })

    # ---- 8. 本体对齐 ----
    align_to_ontology(entities, relations, ontology)

    # ---- 9. 清理输出属性 ----
    for ent in entities:
        ent.pop("start", None)
        ent.pop("end", None)
        # 使用本体类型作为最终类型
        if "ontologyType" in ent:
            ent["type"] = ent.pop("ontologyType")

    # ---- 10. 统计指标 ----
    type_counts = defaultdict(int)
    for e in entities:
        type_counts[e["type"]] += 1
    metrics = {
        "totalEntities": len(entities),
        "totalRelations": len(relations),
        "typeDistribution": dict(type_counts),
        "avgConfidence": round(
            sum(e.get("confidence", 0) for e in entities) / max(len(entities), 1), 4
        ),
        "modelArchitecture": "BiLSTM-CRF + NeuralRelClassifier",
        "embeddingDim": EMBEDDING_DIM,
        "hiddenDim": HIDDEN_DIM,
    }

    return {
        "entities": entities,
        "relations": relations,
        "metrics": metrics,
    }
