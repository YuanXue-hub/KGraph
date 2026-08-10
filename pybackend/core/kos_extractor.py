"""
基于 KOS（知识组织体系）的知识抽取核心算法。

设计思路：以"KOS 词表驱动 + 统计算法（TF-IDF）+ 规则匹配"为核心，不依赖 LLM。
- 内置多领域 KOS 词表（范畴分类 / 主题概念 / 领域术语）
- 滑动窗口最长匹配进行术语识别
- TF-IDF 计算术语重要度
- 按目标分类体系进行范畴归类
- 构建概念层级（属于范畴/属于概念）与关联（相关）关系
"""
import math
import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

# ============================================================
# 内置 KOS 词表（知识组织体系）
# 结构：范畴分类 -> 主题概念 -> 领域术语
# 覆盖农业、信息技术、医药卫生、经济管理、教育文化等领域
# 对应文档中的目标分类体系：PRES/CCT/CASDD/CNE/STKOS/NSTL
# ============================================================

KOS_VOCABULARY: Dict[str, Dict[str, List[str]]] = {
    # 农业科学（对应 CASDD）
    "农业科学": {
        "农作物": ["水稻", "小麦", "玉米", "大豆", "棉花", "茶叶", "甘蔗", "油菜", "高粱", "谷子"],
        "畜禽养殖": ["生猪", "肉牛", "奶牛", "家禽", "绵羊", "山羊", "鸡", "鸭", "鹅", "饲料"],
        "病虫害防治": ["稻瘟病", "纹枯病", "蚜虫", "螟虫", "飞虱", "病害", "虫害", "农药", "防治", "检疫"],
        "土壤肥料": ["土壤", "肥料", "氮肥", "磷肥", "钾肥", "有机肥", "壤土", "盐碱地", "改良"],
        "农业技术": ["育种", "栽培", "灌溉", "温室", "农机", "采收", "嫁接", "轮作", "杂交"],
    },
    # 信息技术（对应 STKOS）
    "信息技术": {
        "人工智能": ["人工智能", "机器学习", "深度学习", "神经网络", "自然语言处理", "计算机视觉",
                  "知识图谱", "大模型", "算法", "训练", "推理", "向量数据库", "嵌入"],
        "软件开发": ["软件", "程序", "代码", "框架", "接口", "数据库", "服务器", "前端", "后端",
                  "微服务", "容器", "部署", "调试", "编译"],
        "网络通信": ["网络", "互联网", "协议", "带宽", "路由器", "云计算", "边缘计算", "5G",
                  "物联网", "区块链", "网络安全", "加密"],
        "数据科学": ["数据", "数据挖掘", "数据分析", "大数据", "数据仓库", "可视化", "统计",
                  "特征工程", "建模", "指标"],
    },
    # 医药卫生（对应 CNE）
    "医药卫生": {
        "疾病": ["糖尿病", "高血压", "冠心病", "肿瘤", "肺炎", "肝炎", "胃炎", "流感",
              "慢性病", "传染病", "症状", "诊断", "预后"],
        "药物": ["药物", "抗生素", "疫苗", "中药", "西药", "处方", "剂量", "疗效",
              "不良反应", "临床试验", "靶向药"],
        "医疗技术": ["手术", "影像", "检验", "内窥镜", "放疗", "化疗", "免疫治疗",
                  "基因检测", "康复", "护理"],
        "公共卫生": ["防疫", "疾控", "健康", "卫生", "流行病学", "筛查", "接种",
                  "隔离", "监测", "防控"],
    },
    # 经济管理（对应 CCT）
    "经济管理": {
        "宏观经济": ["经济", "GDP", "通胀", "通缩", "财政", "货币政策", "利率", "汇率",
                  "贸易", "投资", "消费", "出口", "进口"],
        "企业管理": ["企业", "管理", "战略", "运营", "营销", "供应链", "成本", "利润",
                  "品牌", "客户", "绩效", "组织"],
        "金融市场": ["股票", "债券", "基金", "期货", "银行", "保险", "证券", "风险",
                  "资产", "估值", "收益", "杠杆"],
        "产业经济": ["产业", "产业链", "集群", "园区", "转型升级", "创新驱动", "新动能",
                  "高质量发展", "数字经济", "绿色经济"],
    },
    # 教育文化（对应 PRES）
    "教育文化": {
        "教育教学": ["教育", "教学", "课程", "课堂", "学生", "教师", "学校", "培训",
                  "考核", "素质教育", "职业教育", "高等教育"],
        "科学技术": ["科学", "技术", "研究", "实验", "创新", "专利", "成果", "学术",
                  "论文", "课题", "协作", "转化"],
        "文化遗产": ["文化", "遗产", "文物", "非遗", "博物馆", "考古", "保护", "传承",
                  "文献", "古籍", "遗址"],
        "传播出版": ["出版", "媒体", "传播", "新闻", "期刊", "图书", "版权", "发行",
                  "数字出版", "融媒体"],
    },
}

# 扁平化术语表：术语 -> (范畴, 概念)，便于快速查找
TERM_INDEX: Dict[str, Tuple[str, str]] = {}
for _cat, _concepts in KOS_VOCABULARY.items():
    for _concept, _terms in _concepts.items():
        for _term in _terms:
            TERM_INDEX[_term] = (_cat, _concept)

# 所有术语按长度倒序排列（最长匹配优先）
ALL_TERMS_SORTED: List[str] = sorted(TERM_INDEX.keys(), key=len, reverse=True)

# 实体识别类型 -> 对应的实体 type 标签
ENTITY_TYPE_MAP = {
    "高频术语": "高频术语",
    "主题概念": "主题概念",
    "范畴分类": "范畴分类",
    "组织机构": "组织机构",
    "专家学者": "专家学者",
    "学术期刊": "学术期刊",
}

# 内置组织机构 / 专家学者 / 学术期刊 样例词表（增强识别能力）
ORGANIZATIONS: List[str] = [
    "中国科学院", "中国农业科学院", "清华大学", "北京大学", "浙江大学", "复旦大学",
    "中国医学科学院", "国家自然基金委员会", "科技部", "农业农村部", "教育部", "国家卫健委",
    "世界卫生组织", "联合国粮农组织",
]
EXPERTS: List[str] = [
    "袁隆平", "屠呦呦", "钟南山", "钱学森", "华罗庚", "李四光",
    "施一公", "张文宏", "高福", "陈薇",
]
JOURNALS: List[str] = [
    "Nature", "Science", "Cell", "中国科学", "科学通报", "中华医学杂志",
    "农业科学", "计算机学报", "经济研究",
]


# ============================================================
# 文本预处理
# ============================================================

def preprocess(text: str) -> List[str]:
    """文本预处理：按标点切分为句子片段，便于后续共现统计。"""
    if not text:
        return []
    # 统一全角标点为半角，便于切分
    text = text.replace("\n", "。").replace("\r", "。")
    # 按句号/问号/感叹号/分号切分
    fragments = re.split(r"[。！？!?\.;；]+", text)
    # 过滤空白片段
    return [f.strip() for f in fragments if f.strip()]


# ============================================================
# 术语识别（滑动窗口 + 最长匹配）
# ============================================================

def extract_terms(text: str) -> List[Tuple[str, int, int]]:
    """
    从文本中识别 KOS 词表中的术语，返回 (术语, 起始位置, 结束位置) 列表。
    采用最长匹配优先策略，避免短术语覆盖长术语。
    """
    if not text:
        return []
    results: List[Tuple[str, int, int]] = []
    n = len(text)
    # 记录已匹配的字符位置，避免重叠
    occupied: List[bool] = [False] * n

    # 按术语长度倒序匹配
    for term in ALL_TERMS_SORTED:
        tlen = len(term)
        if tlen > n:
            continue
        start = 0
        while start <= n - tlen:
            # 跳过已被占用的位置
            if any(occupied[start:start + tlen]):
                start += 1
                continue
            if text[start:start + tlen] == term:
                results.append((term, start, start + tlen))
                for k in range(start, start + tlen):
                    occupied[k] = True
                start += tlen
            else:
                start += 1
    # 按位置排序
    results.sort(key=lambda x: x[1])
    return results


def extract_named_entities(text: str) -> Dict[str, List[Tuple[str, int, int]]]:
    """识别组织机构、专家学者、学术期刊等命名实体。"""
    found: Dict[str, List[Tuple[str, int, int]]] = {
        "组织机构": [],
        "专家学者": [],
        "学术期刊": [],
    }
    for name_list, etype in [(ORGANIZATIONS, "组织机构"), (EXPERTS, "专家学者"), (JOURNALS, "学术期刊")]:
        for name in sorted(name_list, key=len, reverse=True):
            start = 0
            while True:
                idx = text.find(name, start)
                if idx < 0:
                    break
                found[etype].append((name, idx, idx + len(name)))
                start = idx + len(name)
    return found


# ============================================================
# TF-IDF 统计
# ============================================================

def compute_tfidf(fragments: List[str], terms_in_doc: Dict[str, int]) -> Dict[str, float]:
    """
    计算文档内术语的 TF-IDF 得分。
    - TF: 术语在文档中的出现频次 / 文档总术语数
    - IDF: log(总片段数 / 包含该术语的片段数 + 1)
    """
    total_terms = sum(terms_in_doc.values()) or 1
    num_fragments = len(fragments) or 1

    # 统计每个术语出现在多少个片段中（DF）
    df: Counter = Counter()
    for frag in fragments:
        frag_terms: Set[str] = set()
        for term in ALL_TERMS_SORTED:
            if term in frag:
                frag_terms.add(term)
        for t in frag_terms:
            df[t] += 1

    tfidf: Dict[str, float] = {}
    for term, freq in terms_in_doc.items():
        tf = freq / total_terms
        idf = math.log((num_fragments + 1) / (df.get(term, 0) + 1)) + 1
        tfidf[term] = round(tf * idf, 4)
    return tfidf


# ============================================================
# 概念归类与关系构建
# ============================================================

def build_concept_entities(
    terms_in_doc: Dict[str, int],
    tfidf: Dict[str, float],
    term_count: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    根据识别出的术语，构建三类实体：高频术语、主题概念、范畴分类。
    返回：(高频术语实体列表, 主题概念实体列表, 范畴分类实体列表)
    """
    # 1. 高频术语实体（按 TF-IDF 排序，取前 N 个）
    sorted_terms = sorted(
        tfidf.items(), key=lambda x: x[1], reverse=True
    )[:term_count]
    term_entities: List[Dict[str, Any]] = []
    for term, score in sorted_terms:
        cat, concept = TERM_INDEX.get(term, ("未知", "未知"))
        term_entities.append({
            "name": term,
            "type": "高频术语",
            "properties": {
                "tfidfScore": score,
                "frequency": terms_in_doc.get(term, 0),
                "concept": concept,
                "category": cat,
            },
        })

    # 2. 主题概念实体（聚合术语所属概念，按概念内术语得分求和排序）
    concept_scores: Dict[str, float] = defaultdict(float)
    concept_to_cat: Dict[str, str] = {}
    concept_term_count: Dict[str, int] = defaultdict(int)
    for term, score in tfidf.items():
        cat, concept = TERM_INDEX.get(term, ("未知", "未知"))
        if concept == "未知":
            continue
        concept_scores[concept] += score
        concept_to_cat[concept] = cat
        concept_term_count[concept] += 1

    sorted_concepts = sorted(
        concept_scores.items(), key=lambda x: x[1], reverse=True
    )[:term_count]
    concept_entities: List[Dict[str, Any]] = []
    for concept, score in sorted_concepts:
        concept_entities.append({
            "name": concept,
            "type": "主题概念",
            "properties": {
                "score": round(score, 4),
                "termCount": concept_term_count[concept],
                "category": concept_to_cat[concept],
            },
        })

    # 3. 范畴分类实体（聚合概念所属范畴，按范畴内概念得分求和排序）
    category_scores: Dict[str, float] = defaultdict(float)
    category_concept_count: Dict[str, int] = defaultdict(int)
    for concept, score in concept_scores.items():
        cat = concept_to_cat.get(concept, "未知")
        category_scores[cat] += score
        category_concept_count[cat] += 1

    sorted_categories = sorted(
        category_scores.items(), key=lambda x: x[1], reverse=True
    )[:term_count]
    category_entities: List[Dict[str, Any]] = []
    for cat, score in sorted_categories:
        category_entities.append({
            "name": cat,
            "type": "范畴分类",
            "properties": {
                "score": round(score, 4),
                "conceptCount": category_concept_count[cat],
            },
        })

    return term_entities, concept_entities, category_entities


def build_relations(
    term_entities: List[Dict[str, Any]],
    concept_entities: List[Dict[str, Any]],
    category_entities: List[Dict[str, Any]],
    fragments: List[str],
    prefix: str = "",
) -> List[Dict[str, Any]]:
    """
    构建关系：
    - 术语 -> 属于概念 -> 主题概念实体
    - 概念 -> 属于范畴 -> 范畴分类实体
    - 术语 -> 相关（同片段共现） -> 术语
    前缀处理：范畴分类前缀拼接
    """
    relations: List[Dict[str, Any]] = []
    term_names = {e["name"] for e in term_entities}
    concept_names = {e["name"] for e in concept_entities}
    category_names = {e["name"] for e in category_entities}

    # 1. 术语 -属于概念-> 概念
    for te in term_entities:
        concept = te["properties"].get("concept")
        if concept and concept in concept_names:
            relations.append({
                "head": te["name"],
                "relation": "属于概念",
                "tail": concept,
                "properties": {"score": te["properties"].get("tfidfScore", 0)},
            })

    # 2. 概念 -属于范畴-> 范畴分类（应用前缀）
    for ce in concept_entities:
        cat = ce["properties"].get("category")
        if cat:
            target_cat = f"{prefix}{cat}" if prefix else cat
            if cat in category_names:
                relations.append({
                    "head": ce["name"],
                    "relation": "属于范畴",
                    "tail": target_cat,
                    "properties": {"score": ce["properties"].get("score", 0)},
                })

    # 3. 术语 -相关-> 术语（基于片段共现）
    co_occurrence: Counter = Counter()
    for frag in fragments:
        frag_terms = [t for t in term_names if t in frag]
        # 两两组合
        for i in range(len(frag_terms)):
            for j in range(i + 1, len(frag_terms)):
                pair = tuple(sorted([frag_terms[i], frag_terms[j]]))
                co_occurrence[pair] += 1
    # 取共现频次 >= 2 的关系
    for (t1, t2), count in co_occurrence.most_common(50):
        if count >= 2:
            relations.append({
                "head": t1,
                "relation": "相关",
                "tail": t2,
                "properties": {"coOccurrence": count},
            })

    return relations


# ============================================================
# 主抽取入口
# ============================================================

def extract(
    text: str,
    kos_config: Dict[str, Any],
    ontology: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    KOS 知识抽取主入口。

    :param text: 待抽取文本
    :param kos_config: KOS 抽取参数，含：
        - termCount: 高频术语数量（默认 10）
        - conceptCount: 高频概念数量（默认 10）
        - categoryCount: 范畴分类数量（默认 10）
        - scoreBasis: 分类得分依据（高频术语/语义关联）
        - weight: 分类体系权重（默认 1）
        - useWeight: 是否考虑权重（是/否）
        - targetSystems: 目标分类体系列表（PRES/CCT/CASDD/CNE/STKOS/NSTL）
        - multiDoc: 是否多文档（是/否）
        - categoryPrefix: 范畴分类前缀
        - returnWords: 是否返回词（是/否）
        - entityTypes: 实体识别类型列表
    :param ontology: 当前图谱模型的本体 Schema（可选，用于类型对齐）
    :return: {entities, relations, duration, writeCount}
    """
    # 参数解析（带默认值）
    term_count = int(kos_config.get("termCount", 10))
    concept_count = int(kos_config.get("conceptCount", 10))
    category_count = int(kos_config.get("categoryCount", 10))
    prefix = kos_config.get("categoryPrefix", "")
    entity_types = kos_config.get("entityTypes", ["高频术语", "主题概念", "范畴分类"])
    use_weight = kos_config.get("useWeight", "是")
    weight = float(kos_config.get("weight", 1))
    return_words = kos_config.get("returnWords", "是")

    # 文本预处理
    fragments = preprocess(text)

    # 术语识别
    matches = extract_terms(text)
    terms_in_doc: Dict[str, int] = Counter()
    for term, _start, _end in matches:
        terms_in_doc[term] += 1

    # TF-IDF 计算
    tfidf = compute_tfidf(fragments, terms_in_doc)

    # 权重处理
    if use_weight == "是" and weight != 1:
        for t in tfidf:
            tfidf[t] = round(tfidf[t] * weight, 4)

    # 构建三类实体
    term_entities, concept_entities, category_entities = build_concept_entities(
        terms_in_doc, tfidf, term_count
    )
    # 按配置截断概念/范畴数量
    concept_entities = concept_entities[:concept_count]
    category_entities = category_entities[:category_count]

    # 命名实体识别（组织机构/专家学者/学术期刊）
    named_entities: List[Dict[str, Any]] = []
    if any(et in entity_types for et in ["组织机构", "专家学者", "学术期刊"]):
        ne_results = extract_named_entities(text)
        if "组织机构" in entity_types:
            for name, _s, _e in ne_results["组织机构"]:
                named_entities.append({
                    "name": name, "type": "组织机构", "properties": {"source": "KOS内置词表"}
                })
        if "专家学者" in entity_types:
            for name, _s, _e in ne_results["专家学者"]:
                named_entities.append({
                    "name": name, "type": "专家学者", "properties": {"source": "KOS内置词表"}
                })
        if "学术期刊" in entity_types:
            for name, _s, _e in ne_results["学术期刊"]:
                named_entities.append({
                    "name": name, "type": "学术期刊", "properties": {"source": "KOS内置词表"}
                })

    # 按 entityTypes 过滤实体
    all_entities: List[Dict[str, Any]] = []
    if "高频术语" in entity_types:
        all_entities.extend(term_entities)
    if "主题概念" in entity_types:
        all_entities.extend(concept_entities)
    if "范畴分类" in entity_types:
        all_entities.extend(category_entities)
    all_entities.extend(named_entities)

    # 构建关系
    relations = build_relations(
        term_entities, concept_entities, category_entities, fragments, prefix
    )

    # 本体对齐：若 ontology 提供了实体类型，尝试将 KOS 类型映射到本体类型
    if ontology:
        all_entities, relations = _align_to_ontology(all_entities, relations, ontology)

    # returnWords 控制是否返回高频术语（默认是）
    if return_words == "否":
        all_entities = [e for e in all_entities if e["type"] != "高频术语"]

    return {
        "entities": all_entities,
        "relations": relations,
        "metrics": {
            "termCount": len(term_entities),
            "conceptCount": len(concept_entities),
            "categoryCount": len(category_entities),
            "namedEntityCount": len(named_entities),
        },
    }


def _align_to_ontology(
    entities: List[Dict[str, Any]],
    relations: List[Dict[str, Any]],
    ontology: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    将 KOS 抽取的实体类型与当前图谱模型的本体 Schema 对齐。
    若本体中存在同义实体类型，则映射；否则保留 KOS 原始类型。
    """
    onto_entities = ontology.get("entities", []) or []
    onto_entity_names = {e.get("name") for e in onto_entities if e.get("name")}

    # KOS 类型 -> 本体类型映射规则（按名称包含关系）
    type_mapping: Dict[str, str] = {}
    kos_types = {"高频术语", "主题概念", "范畴分类", "组织机构", "专家学者", "学术期刊"}
    for kt in kos_types:
        for oe_name in onto_entity_names:
            # 简单包含匹配
            if kt in oe_name or oe_name in kt:
                type_mapping[kt] = oe_name
                break

    for e in entities:
        original_type = e.get("type")
        if original_type in type_mapping:
            e["properties"]["kosType"] = original_type
            e["type"] = type_mapping[original_type]

    return entities, relations
