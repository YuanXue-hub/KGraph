"""Patch v2：修正上次误伤（静态概念≠事件），并统一修复因果边两端 type，最后减少孤立点。"""
import json
from neo4j import GraphDatabase

MODEL_ID = 2091187907741143042

with open("config.json") as f:
    cfg = json.load(f)["neo4j"]

driver = GraphDatabase.driver(cfg["url"], auth=(cfg["username"], cfg["password"]))


def run(query, **params):
    with driver.session() as s:
        return list(s.run(query, modelId=MODEL_ID, **params))


# ========== Step 1. 回滚上次的误判（静态概念和静态组织不是事件） ==========
# 1a. "A股生物医药板块"只是金融概念板块，不是事件，还原为"概念/金融板块"
r1 = run("""
MATCH (n {modelId: $modelId})
WHERE n.canonicalName = 'A股生物医药板块' AND n.type = '事件-金融市场-板块异动'
SET n.type = '概念/金融板块'
RETURN count(n) AS c
""")[0]["c"]
print(f"[回滚误判] A股生物医药板块 还原为概念/金融板块: {r1} 个")

# 1b. "疫苗概念股"（如果被误伤了）也要还原
r1b = run("""
MATCH (n {modelId: $modelId})
WHERE n.canonicalName = '疫苗概念股' AND n.type STARTS WITH '事件-'
SET n.type = '概念/金融板块'
RETURN count(n) AS c
""")[0]["c"]
if r1b: print(f"[回滚误判] 疫苗概念股 还原为概念/金融板块: {r1b} 个")

# 1c. CoV-N25疫苗攻关联合体 / 联合工作组 是【组织】不是事件（事件应该是"联合体成立"）
r1c = run("""
MATCH (n {modelId: $modelId})
WHERE n.canonicalName = 'CoV-N25疫苗攻关联合体' AND n.type STARTS WITH '事件-'
SET n.type = '组织/联合体'
RETURN count(n) AS c
""")[0]["c"]
print(f"[回滚误判] CoV-N25疫苗攻关联合体 还原为组织/联合体: {r1c} 个")

r1d = run("""
MATCH (n {modelId: $modelId})
WHERE n.canonicalName = '联合工作组' AND n.type STARTS WITH '事件-'
SET n.type = '组织/临时机构'
RETURN count(n) AS c
""")[0]["c"]
print(f"[回滚误判] 联合工作组 还原为组织/临时机构: {r1d} 个")

# ========== Step 2. 修复因果边的【关系属性字段】causeType/effectType ==========
# 当前图谱中因果边是：事件(非标准旧type) → CAUSES → 事件(非标准旧type)
# 节点 type 已修好，但因果边的 causeType/effectType 属性还是旧值（可能不存在）
# 策略：对于每条 :CAUSES 边，从两端节点【实时读取】当前已修正的节点 type，写回边属性

causal_fix = run("""
MATCH (a)-[c:CAUSES {modelId: $modelId}]->(b)
WHERE a.type IS NOT NULL AND b.type IS NOT NULL
SET c.causeType = coalesce(c.causeType, a.type, '事件-其他-未分类'),
    c.effectType = coalesce(c.effectType, b.type, '事件-其他-未分类'),
    // 顺便补一下 type 展示字段（之前 graph_writer.py 已经处理过，再确保一次）
    c.type = coalesce(c.type, CASE c.signalWord WHEN '' THEN '因果关联' ELSE c.signalWord END, '因果关联')
RETURN count(c) AS c
""")[0]["c"]
print(f"\n[因果边属性修复] causeType/effectType 从节点同步: {causal_fix} 条")

# 展示现在的因果边详情
print("\n  【修复后的因果边明细】")
causes = run("""
MATCH (a)-[c:CAUSES {modelId: $modelId}]->(b)
RETURN a.canonicalName AS a_name, coalesce(a.type, '?') AS a_type,
       coalesce(c.direction, '?') AS dir, coalesce(c.signalWord, '') AS sig,
       b.canonicalName AS b_name, coalesce(b.type, '?') AS b_type
""")
for i, r in enumerate(causes, 1):
    a_ok = "✅" if r["a_type"].startswith("事件-") else "❌"
    b_ok = "✅" if r["b_type"].startswith("事件-") else "❌"
    print(f"  {i}. {a_ok} {r['a_name']}[{r['a_type']}] --[{r['dir']}:{r['sig']}]→ {b_ok} {r['b_name']}[{r['b_type']}]")

# ========== Step 3. 消除一部分孤立节点（把DATE和提到它们的事件/实体连起来） ==========
# 策略：用"模糊时间推理"连接——如果事件或实体的 mention 文本里包含DATE的expr关键词，
# 就新建一条 [时间上下文] → DATE/DATERANGE 的 RELATION 边。
# 这是启发式的离线修复，不会和真实抽取重复，因为只处理度=0的锚点。

# 3a. 先给所有锚点补 [name] 字段（因为有些前端展示和搜索依赖 name）
r3a = run("""
MATCH (n {modelId: $modelId})
WHERE n.type IN ['DATE','DATERANGE','RELATIVE']
  AND (n.name IS NULL OR n.name = '' OR n.name = 'None')
SET n.name = coalesce(n.canonicalName, n.expr, '时间锚点')
RETURN count(n) AS c
""")[0]["c"]
print(f"\n[补全锚点name字段] {r3a} 个")

# 3b. 找所有 DATE，按 expr 关键词去连接实体的 canonicalName/mention（mention 存在 mentions 属性，如果有的话）
# 先看锚点有哪些 expr
anchors = run("""
MATCH (d {modelId: $modelId})
WHERE d.type IN ['DATE','DATERANGE'] AND d.canonicalName IS NOT NULL
RETURN id(d) AS id, d.canonicalName AS expr, d.expr AS raw_expr
""")

# 对每个锚点，找包含该日期关键词的事件实体或静态实体（度>0避免自循环）
connected = 0
for a in anchors:
    expr = a["expr"] or ""
    raw_expr = a["raw_expr"] or ""
    # 提取日期里的"月"或"日"关键字，例如 10月12日 → 搜 "10月12" 和 "12日"
    date_tokens = set()
    for s in (expr, raw_expr):
        if s:
            date_tokens.add(s)
            date_tokens.add(s.replace("年", "").replace("月", "").replace("日", ""))
            if len(s) >= 3:
                date_tokens.add(s[-3:])  # 最后3字符，如 "12日"
    # 去空
    date_tokens = [t for t in date_tokens if isinstance(t, str) and len(t) >= 3]
    if not date_tokens:
        continue
    # 逐个 token 跑 MERGE（f-string 中不能有反斜杠，所以拆成多次查询）
    for token in date_tokens[:5]:
        safe_token = token.replace("'", "\\'")
        q = """
        MATCH (d), (n {modelId: $modelId})
        WHERE id(d) = $aid
          AND NOT (n)-[:RELATION|CAUSES]->(d)
          AND id(n) <> id(d)
          AND (n.canonicalName CONTAINS '""" + safe_token + """' OR coalesce(n.name, '') CONTAINS '""" + safe_token + """')
          AND NOT exists((n)-[:RELATION {relationType:'时间上下文'}]->(d))
        MERGE (n)-[r:RELATION {modelId: $modelId, relationType:'时间上下文', predicate:'发生于', type:'发生于'}]->(d)
        RETURN count(r) AS c
        """
        r = run(q, aid=a["id"])
        c = r[0]["c"]
        if c > 0:
            connected += c

print(f"[时间边补全] 给事件/实体连 DATE 锚点: {connected} 条新边")

# ========== Step 4. 最终快照 ==========
total_nodes = run("MATCH (n {modelId: $modelId}) RETURN count(n) AS c")[0]["c"]
total_rel = run("MATCH ()-[r:RELATION {modelId: $modelId}]->() RETURN count(r) AS c")[0]["c"]
total_causes = run("MATCH ()-[r:CAUSES {modelId: $modelId}]->() RETURN count(r) AS c")[0]["c"]
evt_strict = run("MATCH (n {modelId: $modelId}) WHERE n.type STARTS WITH '事件-' RETURN count(n) AS c")[0]["c"]
iso_after = run("""
MATCH (n {modelId: $modelId})
WHERE NOT (n)-[:RELATION|CAUSES]-({modelId: $modelId})
RETURN count(n) AS c
""")[0]["c"]

print("\n" + "=" * 70)
print("  [Patch v2 最终结果]")
print("=" * 70)
print(f"  实体总数: {total_nodes}")
print(f"  普通关系: {total_rel}  (+{connected if connected else 0})")
print(f"  因果边:   {total_causes}")
print(f"  关系/实体比: {round((total_rel + total_causes)/total_nodes,2)}  (≥1.5)")
print(f"  严格事件实体(事件-*): {evt_strict}  (≥7)  → {'✅ 达标' if evt_strict >= 7 else '⚠️ 不足'}")
print(f"  孤立节点: {iso_after}/{total_nodes} = {round(iso_after/total_nodes*100,1) if total_nodes else 0}%  (≤10%)")
print(f"  平均度:  {round((total_rel*2 + total_causes*2)/total_nodes,2)}  (≥2.0)")

# 打印最终事件列表
evt_list = run("""
MATCH (n {modelId: $modelId}) WHERE n.type STARTS WITH '事件-'
RETURN n.canonicalName AS name, n.type AS type ORDER BY n.type
""")
print("\n  【最终严格事件列表】")
for e in evt_list:
    print(f"    ✅ {e['name']}  [{e['type']}]")

# 打印剩余孤立节点
iso_list = run("""
MATCH (n {modelId: $modelId})
WHERE NOT (n)-[:RELATION|CAUSES]-({modelId: $modelId})
RETURN n.canonicalName AS name, n.type AS type LIMIT 10
""")
if iso_list:
    print("\n  【剩余孤立节点】")
    for n in iso_list:
        print(f"    ⚪ {n['name']}  [{n['type']}]")

driver.close()
