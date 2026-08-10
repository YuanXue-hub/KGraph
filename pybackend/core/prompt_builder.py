from typing import Any, Dict, List


def build_messages(
    text: str, ontology: Dict[str, Any], mode: str = "zero_shot"
) -> List[Dict[str, str]]:
    """根据本体 Schema 构建对话消息。当前实现 zero_shot 模式。
    当 ontology 为空时，使用通用实体关系抽取（不限制类型）。"""

    entities = ontology.get("entities", []) or []
    relations = ontology.get("relations", []) or []

    # ===== 通用抽取模式：未配置实体/关系类型 =====
    if not entities and not relations:
        system = (
            "你是一个知识图谱抽取专家。请从文本中自由抽取实体和关系，"
            "自动识别文本中的关键实体及其之间的关系。"
        )
        user = (
            "请从以下文本中抽取实体和关系，自由识别文本中的关键实体及其之间的关系。\n\n"
            "## 规则\n"
            "1. 识别文本中的重要实体，如人物、组织、地点、事件、时间、概念等\n"
            "2. 为每个实体推断合适的类型（如：人物、组织、地点、事件、时间、概念、武器、战役等）\n"
            "3. 识别实体之间的关系，关系名称应简洁准确（如：担任、领导、位于、参与、攻击等）\n"
            "4. 实体名称从文本中提取原文\n"
            "5. 尽可能多地抽取有意义的实体和关系\n\n"
            "## 输出格式（严格JSON，不要输出其他内容）\n"
            "{\n"
            '  "entities": [\n'
            '    {"name": "实体名称", "type": "实体类型", "properties": {}}\n'
            "  ],\n"
            '  "relations": [\n'
            '    {"head": "头实体名称", "relation": "关系类型", "tail": "尾实体名称", "properties": {}}\n'
            "  ]\n"
            "}\n\n"
            "## 待抽取文本\n"
            f"{text}"
        )
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    # ===== 本体约束模式：已配置实体/关系类型 =====

    # 实体类型描述
    entity_lines: List[str] = []
    for e in entities:
        props = e.get("properties", []) or []
        if props:
            prop_str = ", ".join(
                f"{p.get('name')}:{p.get('type')}" for p in props
            )
        else:
            prop_str = "无"
        entity_lines.append(f"- {e.get('name')} (属性: {prop_str})")
    entity_section = "\n".join(entity_lines) if entity_lines else "无"

    # 关系类型描述
    relation_lines: List[str] = []
    for r in relations:
        relation_lines.append(
            f"- {r.get('name')} ({r.get('source')} -> {r.get('target')})"
        )
    relation_section = "\n".join(relation_lines) if relation_lines else "无"

    system = (
        "你是一个知识图谱抽取专家。请从文本中抽取实体和关系，"
        "严格按照指定的本体模型输出。"
    )

    user = (
        "请从以下文本中抽取实体和关系，严格按照指定的本体模型输出。\n\n"
        "## 本体模型\n\n"
        "### 实体类型\n"
        f"{entity_section}\n\n"
        "### 关系类型\n"
        f"{relation_section}\n\n"
        "## 规则\n"
        "1. 只抽取上述定义的实体类型和关系类型\n"
        "2. 实体名称从文本中提取原文\n"
        "3. 如果文本中没有匹配的实体或关系，返回空列表\n\n"
        "## 输出格式（严格JSON，不要输出其他内容）\n"
        "{\n"
        '  "entities": [\n'
        '    {"name": "实体名称", "type": "实体类型", "properties": {"属性名": "属性值"}}\n'
        "  ],\n"
        '  "relations": [\n'
        '    {"head": "头实体名称", "relation": "关系类型", "tail": "尾实体名称", "properties": {}}\n'
        "  ]\n"
        "}\n\n"
        "## 待抽取文本\n"
        f"{text}"
    )

    # few_shot 模式预留扩展位（当前仅实现 zero_shot）
    if mode == "few_shot":
        user = (
            "以下为示例，帮助你理解输出格式。\n\n"
            "示例输入: 张三出生于北京。\n"
            "示例输出: "
            '{"entities": [{"name": "张三", "type": "人物", "properties": {}}], '
            '{"name": "北京", "type": "地点", "properties": {}}], '
            '"relations": [{"head": "张三", "relation": "出生于", "tail": "北京", "properties": {}}]}\n\n'
            + user
        )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
