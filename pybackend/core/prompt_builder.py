"""LLM 知识抽取 Prompt（两阶段 · 质量优先版，不考虑因果关系）。

架构（2 次 LLM 调用，聚焦实体 + 关系完整性）：
  阶段1 build_node_messages：抽「节点」—— 静态实体 + 事件实体 + 指代消解链 + 时间锚点
         · 实体只填 mention/canonicalName/type，不填数字 span（span 由代码 find() 定位）
         · 事件实体 type 统一为「事件」，语义全靠 canonicalName 自包含描述
         · 指代词（该院/该公司）不放 entities，放 coreferenceChains
  阶段2 build_relation_messages：抽「关系」—— 注入阶段1 实体表做硬约束
         · 主语/宾语优先从实体表中选（消除幻觉实体 → 消除孤立节点）
         · 每条关系附证据句原文 evidenceText（不填数字偏移，代码定位算 span）

设计原则（质量优先，完整性第一）：
  1. 每次调用只做一类任务，注意力全部给当前子任务（关系密度↑）
  2. 关系抽取受实体表约束 + 代码二次校验（幻觉实体清零）
  3. 指代消解前置（"该院"归并到规范实体，孤立节点↓）
  4. 证据句原文代替数字偏移（span 幻觉问题结构性消除）
  5. 不抽因果边（因果关系后续走图上离线推理，当前 LLM 全部预算给实体/关系召回）
"""
from __future__ import annotations

import json
from typing import Any, Dict, List


def _format_ontology(ontology: Dict[str, Any] | None) -> str:
    """把本体约束压成紧凑字符串（type 枚举优先，未命中才允许自定义）。"""
    if not ontology or not isinstance(ontology, dict):
        return "（无本体约束，type 自由推断）"
    items: List[str] = []
    for k, v in ontology.items():
        if isinstance(v, (str, int, float)):
            items.append(f"- {k}: {v}")
        elif isinstance(v, list):
            items.append(f"- {k}: {', '.join(str(x) for x in v[:12])}")
        elif isinstance(v, dict):
            items.append(f"- {k}: {json.dumps(v, ensure_ascii=False)[:150]}")
    return "\n".join(items[:20]) if items else "（无本体约束，type 自由推断）"


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
# 阶段1：节点抽取（静态实体 + 事件实体 + 指代消解链 + 时间锚点）
# ============================================================================
def build_node_messages(
    text: str,
    ontology: Dict[str, Any] | None = None,
) -> List[Dict[str, str]]:
    onto_str = _format_ontology(ontology)

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
4. **宁全勿漏，数量无上限**：所有能参与关系的名词/事件全部抽，不确定 type 就写最宽泛合理的类别（组织/地点/人物/概念/文件/公司/团队/产品/事件），但不要漏。指代词（该院/该公司/其/他们）不进 entities，放 coreferenceChains.aliases。
"""

    return [
        {"role": "system", "content": "你是严谨的中文知识图谱节点抽取工程师。只输出 JSON 本身，字段不留 null 占位（可空字段除外）。实体宁全勿漏，类型必须遵守枚举约束。"},
        {"role": "user", "content": user_msg},
    ]


# ============================================================================
# 阶段2：关系抽取（注入阶段1 实体表做硬约束 + 证据句原文）
# ============================================================================
def build_relation_messages(
    text: str,
    entity_table_str: str,
    ontology: Dict[str, Any] | None = None,
) -> List[Dict[str, str]]:
    onto_str = _format_ontology(ontology)

    user_msg = f"""## 任务：从「待抽取文本」中抽取实体之间的关系三元组。

### 实体表（关系 subject / object 优先从下列实体名选，命中了就要写完全相同的 canonicalName；如果原文中关键实体确实没出现在下表，**允许**填写它的规范全称，后处理会自动创建占位节点补进图中）
{entity_table_str}

### 输出格式（严格只输出以下 JSON 一段）
```
{{
  "relations": [
    {{"subject": "规范实体名/事件完整短语", "predicate": "关系谓词", "object": "规范实体名/事件完整短语",
      "evidenceText": "支撑本关系的原文完整句子（必须逐字来自原文，代码会校验）",
      "vt_from": "关系有效起点 ISO 或 null", "vt_to": "关系有效终点 ISO 或 null",
      "status": "CURRENT|EXPIRED|NEGATED", "confidence": 0.0}}
  ]
}}
```

### 关系抽取 4 条铁律（图谱完整性 = 召回第一，全部 LLM 注意力给关系密度）
1. **事件实体至少 3 条论元关系**：对每个「事件」实体，输出至少 3 条连接边（不硬凑，但只要原文有证据就必须写出），优先覆盖：
   - **执行主体**：谁发起的（机构/人物/团队）
   - **作用对象**：事件作用于什么（患者/病毒/市场/疫苗/文件/产品/数据）
   - **时间/地点**：何时何地发生（写「发生地点」「发生时间」，对象接时间锚点不强制，但若能对应到具体事件则更好）
   - **承接事件**：该事件之后发生了什么（例如「初步判定新型病毒」之后立即出现的是「送检测序」）
2. **零孤立实体铁律（阶段2必须兑现阶段1的承诺）**：遍历上面实体表中的**每一个**静态实体（机构/地点/人物/文件/概念/公司/团队/产品/项目/学科），**必须确保至少有 1 条关系**（主语或宾语位置）连接到它。如果某个实体在原文中能找到的关系较弱，就回头在原文找证据补一条，哪怕是「包含于」「位于」「发布方」「管辖」「成员」「参与」「关联」「提及」「适用对象」「合作方」「上级单位」「下属机构」这种弱语义连接也行，**绝对不能让它孤立**。
3. **谓词密度拉满，否定/排除/层级/反向/时间 全部要抽**：
   - 否定表述（「排除流感/禽流感/SARS/MERS」「不再担任」「未检出」「无效」）→ status=NEGATED
   - 机构层级与隶属（国家卫健委-主管->广东省疾控中心 / 联防联控机制-派出->督导组 / 某大学-下属->某学院 / 公司-控股->子公司）→ 全部写出
   - 层级分类（「新冠疫苗属于疫苗范畴」「流感属于呼吸道传染病」「某某院士隶属于呼吸病学国家重点实验室」）→ predicate 用「属于」「分类为」「隶属于」
   - 文件政策与适用对象（诊疗方案-发布方->国家卫健委 / 诊疗方案-适用对象->新型冠状病毒感染者 / 管理办法-适用范围->医疗机构）→ 全部写出
   - 事件承接与先后（A 完成后立刻启动 B / 基于 A 的结果发布了 B）→ predicate 用「随后启动」「基于」「紧接」
   - 人员与团队（钟南山院士-担任->专家组组长 / 研究团队-完成->实验）→ 全部写出
   - 市场与金融表象（疫苗攻关联合体成立 关联 生物医药板块表现 / 某公司 发布利好 关联 股价变动）→ 用语义谓词（推动/拉动/带动/关联/影响）写出
4. **时间绑定必须填满 + 去同存异 + 低置信也保留**：
   - 每条关系尽量填 vt_from（原文明确的时间点 ISO），不要都留 null；事件性关系 vt_to 留 null。
   - subject、predicate、object 三个字段**完全相同**的重复三元组合并为一条，取 confidence 最高的那条，不要重复输出。
   - confidence ≥ 0.50 就输出，哪怕证据是间接的（置信=0.50~0.60），也比缺边好。
"""

    return [
        {"role": "system", "content": "你是严谨的中文知识图谱关系抽取工程师。只输出 JSON 本身。主语宾语必须来自给定实体表，每条关系必须有原文证据句。"},
        {"role": "user", "content": user_msg},
    ]
