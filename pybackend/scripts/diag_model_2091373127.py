"""诊断 model_id=2091373127886991361 抽取质量：实体/事件/关系完整性评估。"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from neo4j import GraphDatabase  # noqa: E402

MODEL_ID = 2091373127886991361  # int，匹配 Neo4j 属性存储类型

_cfg_path = Path(__file__).resolve().parent.parent / "config.json"
with open(_cfg_path) as _f:
    _cfg = json.load(_f)["neo4j"]
driver = GraphDatabase.driver(_cfg["url"], auth=(_cfg["username"], _cfg["password"]))


def run(cypher: str, **params) -> List[Dict[str, Any]]:
    with driver.session() as s:
        res = s.run(cypher, modelId=MODEL_ID, **params)
        return [dict(r) for r in res]


def fmt_pct(part: int, total: int) -> str:
    if total == 0:
        return "0.0%"
    return f"{part * 100 / total:.1f}%"


def main() -> None:
    print(f"\n========== KGraph 质量诊断  modelId={MODEL_ID} ==========\n")

    # -------- 1) 基础计数 --------
    stats = run("""
        MATCH (e:Entity {modelId:$modelId}) WITH count(e) AS ents
        OPTIONAL MATCH ()-[r:RELATION {modelId:$modelId}]->() WITH ents, count(r) AS rels
        OPTIONAL MATCH ()-[c:CAUSES {modelId:$modelId}]->() WITH ents, rels, count(c) AS causes
        OPTIONAL MATCH (a:TimeAnchor {modelId:$modelId}) WITH ents, rels, causes, count(a) AS anchors
        RETURN ents, rels, causes, anchors
    """)[0]
    total_ents: int = stats["ents"]
    total_rels: int = stats["rels"]
    total_causes: int = stats["causes"]
    total_anchors: int = stats["anchors"]

    # -------- 2) 事件实体（严格：type=事件-*） --------
    event_rows = run("""
        MATCH (e:Entity {modelId:$modelId})
        WHERE e.type IS NOT NULL AND e.type STARTS WITH '事件-'
        RETURN e.canonicalName AS name, e.type AS type,
               size(coalesce(e.mentions, [])) AS mentions
        ORDER BY type, name
    """)
    strict_events = len(event_rows)

    # 宽松事件（名字/描述里含事件词但 type 不合规）
    loose_event_rows = run("""
        MATCH (e:Entity {modelId:$modelId})
        WHERE (e.type IS NULL OR NOT e.type STARTS WITH '事件-')
          AND (
            toLower(coalesce(e.canonicalName, '')) CONTAINS '事件'
            OR toLower(coalesce(e.type, '')) CONTAINS 'event'
            OR toLower(coalesce(e.type, '')) CONTAINS '事件'
          )
        RETURN e.canonicalName AS name, e.type AS type
        LIMIT 50
    """)
    loose_events = len(loose_event_rows)

    # -------- 3) 孤立节点（度数 = 0） --------
    iso_rows = run("""
        MATCH (e:Entity {modelId:$modelId})
        OPTIONAL MATCH (e)-[r]-()
        WHERE type(r) IN ['RELATION','CAUSES'] AND r.modelId = $modelId
        WITH e, count(r) AS k
        WHERE k = 0
        RETURN e.canonicalName AS name, e.type AS type
        ORDER BY type, name
    """)
    isolated = len(iso_rows)

    # -------- 4) 度/连通性 --------
    degree_stats = run("""
        MATCH (e:Entity {modelId:$modelId})
        OPTIONAL MATCH (e)-[r]-()
        WHERE type(r) IN ['RELATION','CAUSES'] AND r.modelId = $modelId
        RETURN e.canonicalName AS name, e.type AS type, count(r) AS deg
        ORDER BY deg DESC, name ASC
    """)
    degs = [d["deg"] for d in degree_stats]
    avg_deg = (sum(degs) / len(degs)) if degs else 0.0
    top_deg = degree_stats[:15] if degree_stats else []

    # -------- 5) 实体 type 分布（Top 20） --------
    type_dist = run("""
        MATCH (e:Entity {modelId:$modelId})
        WITH coalesce(e.type, 'NULL') AS t, count(e) AS cnt
        RETURN t, cnt ORDER BY cnt DESC LIMIT 25
    """)

    # -------- 6) 关系谓词 Top 30 & status 分布 --------
    rel_pred = run("""
        MATCH ()-[r:RELATION {modelId:$modelId}]->()
        WITH coalesce(r.relationType, coalesce(r.predicate, 'NULL')) AS p,
             count(r) AS cnt
        RETURN p, cnt ORDER BY cnt DESC LIMIT 30
    """)
    rel_status = run("""
        MATCH ()-[r:RELATION {modelId:$modelId}]->()
        WITH coalesce(r.status, 'NULL') AS s, count(r) AS cnt
        RETURN s, cnt ORDER BY cnt DESC
    """)
    negated_rels = run("""
        MATCH (s)-[r:RELATION {modelId:$modelId}]->(o)
        WHERE r.status = 'NEGATED'
        RETURN s.canonicalName AS sub, coalesce(r.relationType, r.predicate) AS p,
               o.canonicalName AS obj
        ORDER BY sub, p, obj
        LIMIT 20
    """)

    # -------- 7) 双时态关系占比（有 vt_from/vt_to） --------
    temporal = run("""
        MATCH ()-[r:RELATION {modelId:$modelId}]->()
        WITH count(r) AS total,
             sum(CASE WHEN r.vt_from IS NOT NULL OR r.vt_to IS NOT NULL THEN 1 ELSE 0 END) AS has_vt,
             sum(CASE WHEN r.vt_from IS NOT NULL AND r.vt_to IS NOT NULL THEN 1 ELSE 0 END) AS has_both
        RETURN total, has_vt, has_both
    """)[0]

    # -------- 8) 关系头/尾覆盖率（至少连一条的实体比例） --------
    covered_ents = run("""
        MATCH (e:Entity {modelId:$modelId})
        WHERE (e)-[:RELATION {modelId:$modelId}]->() OR ()-[:RELATION {modelId:$modelId}]->(e)
        RETURN count(e) AS cnt
    """)[0]["cnt"]

    # -------- 9) 因果边（当前重构后应为 0；记录一下） --------
    cause_list = run("""
        MATCH (s)-[c:CAUSES {modelId:$modelId}]->(o)
        RETURN s.canonicalName AS cause, s.type AS causeType,
               o.canonicalName AS effect, o.type AS effectType,
               c.direction AS dir, c.signalWord AS sw
    """)

    # -------- 10) 时间锚点质量（type分布 & canonicalName是否空 & 孤立锚点） --------
    anchor_quality = run("""
        MATCH (a:TimeAnchor {modelId:$modelId})
        OPTIONAL MATCH (a)-[r_a]-()
        WHERE type(r_a) IN ['RELATION','CAUSES'] AND r_a.modelId=$modelId
        WITH a, count(r_a) AS anch_deg
        WITH count(a) AS total,
             sum(CASE WHEN a.canonicalName IS NULL OR a.canonicalName = '' THEN 1 ELSE 0 END) AS no_cn,
             sum(CASE WHEN a.type = 'DATE' THEN 1 ELSE 0 END) AS dates,
             sum(CASE WHEN a.type = 'DATERANGE' THEN 1 ELSE 0 END) AS ranges,
             sum(CASE WHEN a.type = 'RELATIVE' THEN 1 ELSE 0 END) AS rels,
             sum(CASE WHEN a.type IN ['NOW','OPEN','UNKNOWN'] THEN 1 ELSE 0 END) AS others,
             sum(CASE WHEN anch_deg = 0 THEN 1 ELSE 0 END) AS isolated_anchors
        RETURN total, no_cn, dates, ranges, rels, others, isolated_anchors
    """)
    aq = anchor_quality[0] if anchor_quality else {}

    # =====================================================
    # 打印评估表
    # =====================================================
    def H(title: str) -> None:
        bar = "=" * max(10, len(title.encode("utf-8")) + 4)
        print(f"\n{bar}\n  {title}\n{bar}")

    H("1. 基础指标总览")
    event_pct_target = 0.15  # 目标 ≥15%
    event_pct = strict_events / total_ents if total_ents else 0
    print(f"  实体总数         : {total_ents}")
    print(f"  时间锚点         : {total_anchors}")
    print(f"  普通关系[:RELATION]: {total_rels}")
    print(f"  因果边[:CAUSES]   : {total_causes}（重构后预期=0，后续用图推理补）")
    print(f"  严格事件实体(type=事件-*) : {strict_events}  |  占比 {fmt_pct(strict_events, total_ents)}  |  目标≥{event_pct_target*100:.0f}% → {('✅ 达标' if event_pct >= event_pct_target else '❌ 未达')}")
    if loose_events:
        print(f"  宽松/不合规事件(type≠事件-*但名含事件): {loose_events} 个 → 需靠 L5 归一化")
    print(f"  孤立实体(度数=0) : {isolated}  |  占比 {fmt_pct(isolated, total_ents)}  |  目标≤10% → {('✅ 达标' if total_ents and (isolated/total_ents <= 0.10) else '❌ 未达')}")
    print(f"  实体连至少1条RELATION : {covered_ents}/{total_ents} = {fmt_pct(covered_ents, total_ents)}")
    print(f"  平均度(含所有关系): {avg_deg:.2f}  |  目标≥2.0 → {('✅ 达标' if avg_deg >= 2.0 else '❌ 未达')}")

    H("2. 严格事件实体清单（type=事件-*）")
    if not event_rows:
        print("  ⚠️  0 个。本次抽取未按要求把动词短语建模为独立事件节点。")
    else:
        etype_counter: Counter = Counter(e["type"] for e in event_rows)
        print(f"  事件 type 分布（{len(etype_counter)} 种）:")
        for t, c in etype_counter.most_common():
            print(f"    {t}: {c} 个")
        print("\n  事件实体详情（全部）:")
        for e in event_rows:
            print(f"    · {e['name']} ｜ type={e['type']} ｜ mentions={e['mentions']}")

    if loose_event_rows:
        H("2b. 宽松不合规事件（type 格式需 L5 归一化修正，取前 20）")
        for e in loose_event_rows[:20]:
            print(f"    · {e['name']} ｜ 当前 type={e['type']}")

    H("3. 实体 type 分布 Top 20（全部类型）")
    for row in type_dist:
        print(f"  {row['t']:<22} {row['cnt']:>3}  个  ({fmt_pct(row['cnt'], total_ents)})")

    H("4. 关系谓词 Top 30 + 时态覆盖率")
    t = temporal
    if total_rels:
        print(f"  带 vt_from/vt_to 关系 : {t['has_vt']}/{t['total']} = {fmt_pct(t['has_vt'], t['total'])}")
        print(f"  vt_from AND vt_to 齐全 : {t['has_both']}/{t['total']} = {fmt_pct(t['has_both'], t['total'])}")
    print("  谓词频次:")
    for row in rel_pred:
        print(f"    {row['p']:<18} {row['cnt']:>3} 次")
    print("\n  关系 status 分布:")
    for row in rel_status:
        print(f"    {row['s']:<10} {row['cnt']:>3} 条")
    if negated_rels:
        print(f"\n  NEGATED(反事实) 关系样本（共查到 ≥{len(negated_rels)} 条）:")
        for r in negated_rels:
            print(f"    {r['sub']} --[{r['p']}]→ {r['obj']}")

    H("5. 节点度数 Top 15（连通性，越大越好）")
    for d in top_deg:
        mark = " ⭐HUB" if d["deg"] >= 5 else ""
        print(f"  度={d['deg']:<3} type={str(d['type'])[:20]:<22} {d['name']}{mark}")
    if isolated:
        print(f"\n  孤立节点（度数=0，共 {isolated} 个，取前 15）:")
        for i in iso_rows[:15]:
            print(f"    · {i['name']} ｜ type={i['type']}")

    H("6. 时间锚点质量")
    if aq:
        print(f"  锚点总数       : {aq['total']}")
        print(f"  canonicalName空: {aq['no_cn']} 个 → L5 归一化应修复为 expr 回填")
        print(f"  DATE / DATERANGE / RELATIVE / 其他 : {aq['dates']} / {aq['ranges']} / {aq['rels']} / {aq['others']}")
        print(f"  孤立锚点(无连边): {aq['isolated_anchors']} 个 → 建议 W1 校验墙强制至少连 1 条边")

    H("7. 因果边（[:CAUSES]，本次重构后预期=0，记录用于对比）")
    if not cause_list:
        print("  0 条因果边入库 → 符合 T2 废弃后预期。后续走 Semantica 式图上后推理。")
    else:
        print(f"  {len(cause_list)} 条因果边（可能是旧模型或旧版本遗留）:")
        for c in cause_list[:20]:
            print(f"    {c['cause']} [{c['causeType']}] --[{c['dir']}/{c['sw']}]→ {c['effect']} [{c['effectType']}]")

    # -------- 综合打分 --------
    H("📊 完整性综合评分（6 项加权）")
    scores = {}
    scores["事件覆盖率(15%权重)"] = min(1.0, event_pct / 0.15) if total_ents else 0.0
    scores["孤立节点≤10%"] = max(0.0, 1 - (isolated / total_ents - 0.10) * 10) if total_ents else 0.0
    scores["平均度≥2.0(15%权重)"] = min(1.0, avg_deg / 2.0)
    scores["关系覆盖率(≥85%)"] = covered_ents / total_ents / 0.85 if total_ents else 0.0
    scores["时态绑定率(≥50%)"] = (t["has_vt"] / total_rels) / 0.50 if total_rels else 0.0
    scores["事件type格式率(=100%)"] = strict_events / max(1, strict_events + loose_events)
    # 总分
    weights = {"事件覆盖率(15%权重)": 0.20, "孤立节点≤10%": 0.18, "平均度≥2.0(15%权重)": 0.15,
               "关系覆盖率(≥85%)": 0.17, "时态绑定率(≥50%)": 0.15, "事件type格式率(=100%)": 0.15}
    total_score = sum(min(1.0, max(0.0, scores[k])) * w for k, w in weights.items())
    for k, w in weights.items():
        s = min(1.0, max(0.0, scores[k]))
        star = "⭐" if s >= 0.90 else "✅" if s >= 0.70 else "⚠️" if s >= 0.40 else "❌"
        print(f"  {star} {k:<26} {s*100:5.1f}/100  (权重 {w*100:.0f}%)")
    print(f"\n  🏁 加权总分: {total_score*100:5.1f}/100")
    print()


if __name__ == "__main__":
    try:
        main()
    finally:
        try:
            driver.close()
        except Exception:
            pass
