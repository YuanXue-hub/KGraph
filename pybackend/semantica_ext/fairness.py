"""Semantica 公平校验墙：对 Semantica 抽取结果应用与 KGraph W1-W5 等价的后处理。

公平性说明（对比实验用）：
  KGraph 的抽取结果默认经过 W1-W5 质量管道（span 修正 / 时态交换 / 实体消歧 /
  因果环标记 / 低置信标记），Semantica 原生输出无任何后处理。直接对比时，
  KGraph 的分数含校验墙增益——为隔离「prompt 设计」与「后处理规则」两个变量，
  本模块把等价规则应用于 Semantica 结果，且**可在前端开关**：
    fairness=on  → 应用（对比两套 prompt + 同规则后处理的净效果）
    fairness=off → 不应用（对比两套框架的端到端原生效果）

规则对齐 KGraph extraction_validator（宽松策略，只修不删）：
  FW1 span 合法性：越界夹紧，mention 错位就地修正
  FW2 时态一致性：vt_from > vt_to 交换
  FW3 实体消歧：完全相等合并；Jaccard≥0.85 近邻合并（别名替换不删）
  FW4 关系去重：同 (head, predicate, tail) 保留最高置信度
  FW5 低置信标记：conf<0.10 标 lowConfidence（不删）
"""
from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any, Dict, List


def _jaccard(a: str, b: str) -> float:
    """与 KGraph validator 同式：字符集 Jaccard。"""
    if not a or not b:
        return 0.0
    sa, sb = set(a), set(b)
    return len(sa & sb) / len(sa | sb)


def apply_fairness_wall(result: Dict[str, Any], text: str) -> Dict[str, Any]:
    """对 run_semantica_extraction 的返回值应用等价后处理，返回带 fairnessReport 的新结果。"""
    report: List[str] = []
    ntext = len(text or "")

    # ---- FW1 span 合法性（越界夹紧 + mention 错位修正）----
    for e in result.get("entities", []):
        sp = e.get("span") or {}
        if sp.get("end", 0) > 0:
            start, end = sp.get("start", 0), sp.get("end", 0)
            if start < 0 or end >= ntext:
                start, end = max(0, min(start, ntext - 1)), max(0, min(end, ntext - 1))
                e["span"] = {"start": start, "end": end}
                report.append(f"FW1: 实体「{e['name']}」span 越界已夹紧")
            actual = text[start:end + 1] if 0 <= start <= end < ntext else ""
            if actual and e.get("mention") and actual != e["mention"]:
                e["mention"] = actual  # 就地修正，不删
                report.append(f"FW1: 实体「{e['name']}」mention 错位已修正")

    # ---- FW2 时态一致性 ----
    for r in result.get("relations", []):
        vf, vt = r.get("vt_from"), r.get("vt_to")
        if vf and vt and vf > vt:
            r["vt_from"], r["vt_to"] = vt, vf
            report.append(f"FW2: 「{r['head']}-{r['relation']}->{r['tail']}」vt 反序已交换")

    # ---- FW3 实体消歧（完全相等合并 + 近邻别名合并，不删实体）----
    entities = result.get("entities", [])
    kept: List[Dict[str, Any]] = []
    alias_map: Dict[str, str] = {}
    for e in entities:
        dup = None
        for k in kept:
            if k["name"] == e["name"] and k["type"] == e["type"]:
                dup = k
                break
        if dup:
            # 完全相等：合并 span（保留更早的），计数 +1
            report.append(f"FW3: 实体「{e['name']}」重复已合并")
            continue
        near = next((k for k in kept
                     if k["type"] == e["type"] and _jaccard(k["name"], e["name"]) >= 0.85), None)
        if near:
            alias_map[e["name"]] = near["name"]  # 近邻：别名替换，不删
            report.append(f"FW3: 「{e['name']}」≈「{near['name']}」已作别名映射")
            continue
        kept.append(e)
    result["entities"] = kept

    # 关系引用重定向到合并后规范名
    for r in result.get("relations", []):
        if r.get("head") in alias_map:
            r["head"] = alias_map[r["head"]]
        if r.get("tail") in alias_map:
            r["tail"] = alias_map[r["tail"]]

    # ---- FW4 三元组去重（同键保留最高置信度）----
    best: Dict[tuple, Dict[str, Any]] = {}
    order: List[tuple] = []
    for r in result.get("relations", []):
        key = (r.get("head"), r.get("relation"), r.get("tail"))
        if key in best:
            if (r.get("confidence") or 0) > (best[key].get("confidence") or 0):
                best[key] = r
            report.append(f"FW4: 「{key[0]}-{key[1]}->{key[2]}」重复三元组已去重")
        else:
            best[key] = r
            order.append(key)
    result["relations"] = [best[k] for k in order]

    # ---- FW5 低置信标记（不删）----
    for r in result.get("relations", []):
        if (r.get("confidence") or 1.0) < 0.10:
            r["lowConfidence"] = True
            report.append(f"FW5: 「{r['head']}-{r['relation']}->{r['tail']}」低置信已标记")

    result["fairnessReport"] = {
        "applied": True,
        "issueCount": len(report),
        "issues": report[:100],  # 截断防爆
    }
    return result
