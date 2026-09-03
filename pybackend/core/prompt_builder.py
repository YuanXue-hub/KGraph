"""LLM 知识抽取 Prompt（两阶段 · 谓词治理 + 时间标定版）。

架构（2 次 LLM 调用，聚焦实体 + 关系完整性）：
  阶段1 build_node_messages：抽「节点」—— 静态实体 + 事件实体 + 指代消解链 + 时间锚点
         · 实体只填 mention/canonicalName/type，不填数字 span（span 由代码 find() 定位）
         · 事件实体 type 统一为「事件」，语义全靠 canonicalName 自包含描述
         · 指代词（该院/该公司）不放 entities，放 coreferenceChains
  阶段2 build_relation_messages：抽「关系」—— 注入阶段1 实体表做硬约束
         · 主语/宾语优先从实体表中选（消除幻觉实体 → 消除孤立节点）
         · 每条关系附证据句原文 evidenceText（不填数字偏移，代码定位算 span）
         · 谓词锚点词表约束（参照 Semantica：标准谓词 + 允许语义变体，禁泛化词）
         · 时间有效性规则 + 信号强度标定 + 少样本示例（参照 Semantica temporal prompt）

类型指令双形态（参照 Semantica entity_types_instruction / relation_types_instruction）：
  · 用户/本体配置了实体类型或关系类型 → 注入「优先类型」指令（允许相近变体）
  · 未配置 → 注入内置默认词表（含 few-shot 示例）

设计原则：
  1. 每次调用只做一类任务，注意力全部给当前子任务
  2. 关系抽取受实体表约束 + 谓词词表锚定 + 代码二次校验
  3. 指代消解前置（"该院"归并到规范实体，孤立节点↓）
  4. 证据句原文代替数字偏移（span 幻觉问题结构性消除）
  5. 不抽因果边（因果关系后续走图上离线推理；普通关系中的因果谓词按词表正常抽取）
"""
from __future__ import annotations

import json
from typing import Any, Dict, List


# ============================================================================
# 默认词表（用户/本体未配置时启用）
# ============================================================================

# 实体类型默认词表（OntoNotes 风格中文化 + few-shot 示例，参照 Semantica 4.1）
_DEFAULT_ENTITY_TYPES = """实体类型从下列默认类型中选择最合适的一项：
- 人物：人名、职务身份（如「李小明」「王芳律师」「张敏法官」）
- 组织：政府机关、事业单位、社会团体、司法机构（如「北京市朝阳区人民法院」「国家卫健委」「北京天驰律师事务所」）
- 公司：企业、商户、品牌（如「捷信消费金融有限公司」）
- 地点：国家、城市、区域、场所（如「广州市」「朝阳区」）
- 政策文件：法律法规、公约、管理办法、方案、报告（如「《互联网金融逾期债务催收自律公约（试行）》」）
- 产品：软硬件、商品、药物、疫苗
- 团队：研究团队、专家组、工作组、板块
- 概念：学科、技术、疾病、权利、数值指标等抽象名词（如「名誉权」「贷款本金及利息」）
- 事件：发生过的动作/事件（type 统一填「事件」两个字，canonicalName 为完整动宾短语）

类型不明确时选语义最接近的类别，允许适度变体（如「研究所」「律所」→ 组织）。"""

# 关系谓词默认词表（通用 + 因果，参照 Semantica 4.2 词表 + 中文领域适配）
_DEFAULT_RELATION_TYPES = """关系谓词从下列默认词表中选择（允许语义等价变体，如「隶属」→「隶属于」）：
- 归属层级：属于、隶属于、位于、包含、管辖、主管、控股、下属机构
- 角色行为：担任、任职于、发布、印发、创建、成立、提交、受理、审理、起诉、反诉、寄送、拨打、赔偿
- 协作交互：合作、参与、使用、采用、依赖、竞争、支持
- 因果传导：导致、引发、源于、起因于、促成、促进、阻碍、抑制、随后启动、随后发生、基于
- 事件论元角色（事件实体作为 subject 时连接参与者）：执行者、作用对象、发生于、原告、被告、案由、请求者、被请求者、接收者、参与方
- 语义关联（弱）：关联、提及、涉及 —— 当语义过于间接、找不到更具体谓词时使用

谓词选择优先级：① 原文的具体动作动词（「拨打催收电话」→ 谓词「拨打」）；② 词表中的标准谓词；③ 弱谓词兜底。"""


# ============================================================================
# 类型指令构造（双形态：用户配置优先，否则默认词表）
# ============================================================================

def _ontology_lists(ontology: Dict[str, Any] | None) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """从 ontology dict 中取出实体类型/关系类型列表（Java buildOntology 结构）。"""
    if not ontology or not isinstance(ontology, dict):
        return [], []
    ents = ontology.get("entities") or []
    rels = ontology.get("relations") or []
    ents = [e for e in ents if isinstance(e, dict) and str(e.get("name") or "").strip()]
    rels = [r for r in rels if isinstance(r, dict) and str(r.get("name") or "").strip()]
    return ents, rels


def _entity_types_instruction(ontology: Dict[str, Any] | None) -> str:
    """实体类型指令：配置了 → 优先类型列表；未配置 → 默认词表（参照 Semantica 双形态）。"""
    ents, _ = _ontology_lists(ontology)
    if not ents:
        return _DEFAULT_ENTITY_TYPES
    lines: List[str] = ["优先实体类型（用户/本体配置，type 必须优先从下列选择）："]
    for e in ents[:20]:
        name = str(e.get("name")).strip()
        desc = str(e.get("description") or "").strip()
        lines.append(f"- {name}" + (f"：{desc[:60]}" if desc else ""))
    lines.append(
        "若某实体不适合任何优先类型，可选优先列表中最接近的类型，或语义相近的类型变体；"
        "事件实体 type 仍统一填「事件」。"
    )
    return "\n".join(lines)


def _relation_types_instruction(ontology: Dict[str, Any] | None) -> str:
    """关系谓词指令：配置了 → 优先谓词列表；未配置 → 默认词表（参照 Semantica 双形态）。"""
    _, rels = _ontology_lists(ontology)
    if not rels:
        return _DEFAULT_RELATION_TYPES
    lines: List[str] = ["优先关系谓词（用户/本体配置，predicate 必须优先从下列选择，允许语义等价变体）："]
    for r in rels[:20]:
        name = str(r.get("name")).strip()
        src = str(r.get("source") or "").strip()
        tgt = str(r.get("target") or "").strip()
        hint = f"（{src}→{tgt}）" if src and tgt and src != "实体" and tgt != "实体" else ""
        lines.append(f"- {name}{hint}")
    lines.append(
        "词表未覆盖的关系可使用原文的具体动作动词或语义等价变体；"
        "弱语义兜底谓词（关联/提及/涉及）仅当找不到更具体谓词时使用且 confidence ≤ 0.50。"
        "禁止使用「实施」「涉及对象」这类不携带关系语义信息的泛化谓词。"
    )
    return "\n".join(lines)


def format_entity_table(entities: List[Dict[str, Any]], max_items: int = 80) -> str:
    """把阶段1 的实体清单格式化为约束表，注入阶段2 Prompt。"""
    lines: List[str] = []
    for i, e in enumerate(entities, 1):
        name = str(e.get("canonicalName") or "").strip()
        etype = str(e.get("type") or "").strip()
        if not name:
            continue
        lines.append(f"{i}. {name} ｜ {etype}")
        if len(lines) >= max_items:
            break
    if not lines:
        return "（实体表为空）"
    return "\n".join(lines)


# ============================================================================
# 时间有效性抽取规则（参照 Semantica 4.3 中译：标定表 + few-shot）
# ============================================================================

_TEMPORAL_RULES = """### 时间有效性抽取规则（vt_from / vt_to / confidence）
- vt_from：ISO 8601 日期或原文中指示该关系生效的确切表述。不存在时间信号时设为 null。
- vt_to：ISO 8601 日期或原文中指示该关系终止的确切表述。**关系是否已结束由 vt_to 表达**：「至今/目前/现任」等开放式留空；「曾任」「已卸任」「已于X年终止」填明确终止时间。
- **不要编造或猜测日期**。如果原文中某关系不存在时间信号，则 vt_from 和 vt_to 均设为 null。
- **原文明确否定的关系**（「传闻不实」「予以否认」「并无此事」）：仍然抽取，但**谓词直接使用否定表述**（如「并无冲突」「未发生」「并未担任」），使关系本身携带否定语义。

时间信号强度标定（confidence 校准参考）：
1.00 = 完整日期（2026-09-15）
0.90 = 明确年月（2026-03）
0.85 = 仅明确年份（「2021年起」「自2019年」）
0.75 = 季度（2023年Q3）
0.65 = 具名季节或近似范围（「2022年夏」「2020年代初」）
0.50 = 模糊相对但有可计算锚点（「去年」「三个月前」）
0.35 = 极其模糊的相对表达（「近期」「近年来」「此前」）
无时间信号 = 不填 vt

小样本示例（不要在输出中包含这些）：
- 原文「2026年9月15日，法院立案受理该案」→ vt_from="2026-09-15", vt_to=null, confidence=0.95
- 原文「2026年7月至8月期间，公司多次拨打催收电话」→ vt_from="2026-07", vt_to="2026-08", confidence=0.90
- 原文「张某曾任该公司CEO，2024年6月卸任」→ vt_from=null, vt_to="2024-06", confidence=0.90
- 原文「传闻两家公司合并，公司公告予以否认」→ predicate 用否定表述「并未合并」, vt_from=null, vt_to=null, confidence=0.90
- 原文「公司一贯遵守行业规范」（无时间信号）→ vt_from=null, vt_to=null, confidence=0.50"""


# ============================================================================
# 阶段1：节点抽取（静态实体 + 事件实体 + 指代消解链 + 时间锚点）
# ============================================================================
def build_node_messages(
    text: str,
    ontology: Dict[str, Any] | None = None,
) -> List[Dict[str, str]]:
    type_instr = _entity_types_instruction(ontology)

    user_msg = f"""## 任务：从「待抽取文本」中抽取知识图谱的全部节点。只抽节点，不抽关系。

### 输出格式（严格只输出以下 JSON 一段，不要任何解释/markdown/思考过程）
```
{{
  "docTime": "文档成文时间 ISO 字符串或 null",
  "entities": [
    {{"mention": "原文片段", "canonicalName": "归一化标准名", "type": "实体类型"}}
  ],
  "coreferenceChains": [
    {{"canonicalName": "规范实体名（必须与 entities 中某条一致）", "aliases": ["简称1", "缩写2", "别名3", "指代词4"]}}
  ],
  "timeAnchors": [
    {{"expr": "原文时间表达式逐字", "type": "DATE|DATERANGE|RELATIVE|NOW|OPEN|UNKNOWN", "normISO": "标准ISO或null", "precision": "day|month|quarter|year|unknown", "relativeAnchor": "RELATIVE时写依赖锚点，否则null"}}
  ]
}}
```

### 节点抽取 4 条铁律（完整性优先级最高，全部预算给实体召回）
1. **canonicalName 别名归一化 + 简称全入库**：同一客观实体的不同表述（如「广东省疾控中心」/「广东省疾病预防控制中心」/「省疾控」；「广州市卫生健康委员会」/「广州市卫健委」/「市卫健委」；「康泰瑞普生物」/「康泰生物」）**必须**合并为同一个 canonicalName（选最长最规范的全称），所有简称/缩写/局部叫法**全部**放进对应 coreferenceChains 的 aliases 数组。严禁为同一个客观实体创建 2 个不同的 entities 条目。
2. **零孤立节点铁律（抽前预判）**：你抽取的每一个静态名词实体（机构/地点/人物/概念/文件/公司/股票板块/研究团队/试验/政策/产品/项目/学科），**必须**能在原文中找到至少一条可以连接它的关系。纯数值（289例、12.5%）、纯修饰形容词（严重的/紧急的）、无法挂到关系上的零散属性不抽成独立实体。
3. **事件实体 = 完整动词短语（事件覆盖率拉满）**：
   - 事件 type 统一填「事件」两个字；
   - canonicalName 必须是「主体+动词(+对象)+必要修饰」的完整动宾短语，如「广州市第八人民医院收治聚集性发热病例」「国家药监局启动疫苗应急审批绿色通道」「康泰瑞普生物连续三个交易日涨停」。
   - 所有发生过的动作/事件全部抽，哪怕原文只提了一句话也要建事件实体。
   - 绝对禁止只写「接诊」「启动」「发布」这种裸动词，也禁止只写「发热病例」「涨停」这种半截短语。
4. **宁全勿漏，数量无上限**：所有能参与关系的名词/事件全部抽，但不要漏。指代词（该院/该公司/其/他们）不进 entities，放 coreferenceChains.aliases。

### 实体类型约束
{type_instr}

## 待抽取文本（实体只能来自这段原文，禁止使用任何示例中的内容）
```
{text}
```
"""

    return [
        {"role": "system", "content": "你是严谨的中文知识图谱节点抽取工程师。只输出 JSON 本身，字段不留 null 占位（可空字段除外）。实体宁全勿漏，类型优先遵守类型约束。"},
        {"role": "user", "content": user_msg},
    ]


# ============================================================================
# 阶段2：关系抽取（注入阶段1 实体表做硬约束 + 谓词词表 + 证据句原文 + 时间标定）
# ============================================================================
def build_relation_messages(
    text: str,
    entity_table_str: str,
    ontology: Dict[str, Any] | None = None,
) -> List[Dict[str, str]]:
    rel_instr = _relation_types_instruction(ontology)

    user_msg = f"""## 任务：从「待抽取文本」中提取实体之间的关系，并为每条关系附带时间有效性信息。
返回结果为 JSON 对象，包含键 "relations"。每个关系必须包含：
'subject'、'predicate'、'object'、'evidenceText'、'vt_from'、'vt_to'、'confidence'。

### 实体表（subject / object 参考下列实体名；若原文中关键实体不在表内，允许填写其规范全称，后处理会补占位节点）
{entity_table_str}

### 输出格式（严格只输出以下 JSON 一段）
```
{{
  "relations": [
    {{"subject": "规范实体名/事件完整短语", "predicate": "关系谓词", "object": "规范实体名/事件完整短语",
      "evidenceText": "支撑本关系的原文完整句子（必须逐字来自原文，代码会校验）",
      "vt_from": "ISO 日期或 null", "vt_to": "ISO 日期或 null", "confidence": 0.0}}
  ]
}}
```

### 关系谓词指引（使用能够准确描述实体连接方式的适当谓词）
{rel_instr}

{_TEMPORAL_RULES}

### 指令
1. 仅从下面提供的文本中提取关系，证据句必须逐字来自原文。
2. 不要包含上述小样本示例中的任何关系。
3. 使用实体表中的实体名作为 subject / object 的参考（命中即写完全相同的 canonicalName）。
4. 谓词优先从词表中选择，允许语义等价变体；禁止使用「实施」「涉及对象」这类不携带关系语义的泛化谓词，「涉及/关联/提及」仅作兜底。
5. **穷尽提取**：尽量找出文本中所有可提取的关系，宁多勿漏。特别是——每个事件实体都要连接它的执行主体（谁做的）、作用对象（对谁/什么做的）和后续承接事件（之后发生了什么）；原文明确否定的传闻关系也要抽，谓词直接用否定表述（如「并无冲突」「未发生」）。
6. subject、predicate、object 完全相同的重复三元组合并为一条，取 confidence 最高的。

## 待提取的文本（关系与证据句只能来自这段原文，禁止使用任何示例中的内容）
```
{text}
```
"""

    return [
        {"role": "system", "content": "你是严谨的中文知识图谱关系抽取工程师。只输出 JSON 本身，每条关系必须有原文证据句。"},
        {"role": "user", "content": user_msg},
    ]
