"""离线修复 model_id=2091187907741143042 已入库的脏数据：
   A. 事件 type 归一化（"金融事件"→"事件-金融市场-板块异动" 等标准格式）
   B. DATE/DATERANGE 锚点 canonicalName=None 修复（用 expr 补）
"""
import json
from neo4j import GraphDatabase

MODEL_ID = 2091187907741143042

with open("config.json") as f:
    cfg = json.load(f)["neo4j"]

driver = GraphDatabase.driver(cfg["url"], auth=(cfg["username"], cfg["password"]))


def run(query, **params):
    with driver.session() as s:
        return list(s.run(query, modelId=MODEL_ID, **params))


# ========== 修复前快照 ==========
before_evt = run("""
MATCH (n {modelId: $modelId}) WHERE n.type STARTS WITH '事件-' RETURN count(n) AS c
""")[0]["c"]
before_loose = run("""
MATCH (n {modelId: $modelId})
WHERE toLower(n.type) CONTAINS '事件' AND NOT (n.type STARTS WITH '事件-')
RETURN n.canonicalName AS name, n.type AS type ORDER BY n.type
""")
before_date_null = run("""
MATCH (n {modelId: $modelId})
WHERE (n.type IN ['DATE','DATERANGE','RELATIVE']) AND (n.canonicalName IS NULL OR n.canonicalName = 'None')
RETURN count(n) AS c
""")[0]["c"]

print(f"[修复前] 严格事件实体: {before_evt} 个")
print(f"[修复前] 宽松待修复事件: {len(before_loose)} 个")
for e in before_loose:
    print(f"    待修: {e['name']}  [旧type={e['type']}]")
print(f"[修复前] 锚点 canonicalName=None: {before_date_null} 个")

# ========== A. 事件 type 归一化（按关键词 + 旧 type 双匹配） ==========
# A1. 按 canonicalName 关键词做精确转换（优先级最高）
KEYWORD_UPDATES = [
    ("应急响应", "事件-应急响应-启动"),
    ("消杀", "事件-医疗公卫-消杀"),
    ("休市", "事件-行政措施-休市"),
    ("绿色通道", "事件-政策审批-应急绿色通道"),
    ("审批绿色通道", "事件-政策审批-应急绿色通道"),
    ("板块", "事件-金融市场-板块异动"),
    ("上涨", "事件-金融市场-板块异动"),
    ("估值修复", "事件-金融市场-板块异动"),
    ("涨停", "事件-金融市场-个股涨停"),
    ("接诊", "事件-医疗公卫-接诊"),
    ("测序", "事件-医疗公卫-测序"),
    ("发布", "事件-行政发布-通告"),
    ("通报", "事件-行政发布-通告"),
    ("排查", "事件-医疗公卫-排查"),
    ("排除", "事件-医疗公卫-排查"),
    ("攻关", "事件-组织成立-攻关小组"),
    ("联合", "事件-组织成立-攻关小组"),
    ("防控预期", "事件-医疗公卫-防控"),
    ("发现与快速响应", "事件-应急响应-启动"),
    ("政策的落地", "事件-政策审批-应急绿色通道"),
]

kw_total_updated = 0
for kw, std_type in KEYWORD_UPDATES:
    r = run("""
    MATCH (n {modelId: $modelId})
    WHERE (toLower(n.type) CONTAINS '事件' OR n.type IN ['DATE','DATERANGE'] OR n.canonicalName CONTAINS $kwMatch)
      AND NOT (n.type STARTS WITH '事件-')
      AND (n.canonicalName CONTAINS $kwMatch OR coalesce(n.name, '') CONTAINS $kwMatch)
    SET n.type = $std_type
    RETURN count(n) AS c
    """, kwMatch=kw, std_type=std_type)
    c = r[0]["c"]
    if c > 0:
        kw_total_updated += c
        print(f"  [A1 关键词] 含'{kw}' → {std_type} : 更新 {c} 个")

# A2. 旧 type 变体兜底（A1 没命中的，按旧 type 字符串批量映射）
VARIANT_UPDATES = [
    ("金融事件", "事件-其他-金融"),
    ("公共卫生事件", "事件-医疗公卫-防控"),
    ("政策事件", "事件-政策发布-通告"),
    ("政策/事件", "事件-政策发布-通告"),
    ("事件/响应", "事件-应急响应-启动"),
    ("事件/工作", "事件-医疗公卫-消杀"),
    ("事件/状态", "事件-行政措施-休市"),
    ("事件/机制", "事件-应急响应-启动"),
    ("市场事件", "事件-金融市场-板块异动"),
    ("事件", "事件-其他-未分类"),  # 最后兜底：只写"事件"两字的
]

var_total_updated = 0
for old_variant, default_type in VARIANT_UPDATES:
    r = run("""
    MATCH (n {modelId: $modelId})
    WHERE n.type = $oldVar AND NOT (n.type STARTS WITH '事件-')
    SET n.type = $newType
    RETURN count(n) AS c
    """, oldVar=old_variant, newType=default_type)
    c = r[0]["c"]
    if c > 0:
        var_total_updated += c
        print(f"  [A2 变体] type='{old_variant}' → {default_type} : 更新 {c} 个")
print(f"\n[A 事件type归一化总计] 关键词命中 {kw_total_updated} + 变体兜底 {var_total_updated} = {kw_total_updated + var_total_updated} 个")

# ========== B. 锚点 canonicalName=None → 用 expr 或 name 回填 ==========
r = run("""
MATCH (n {modelId: $modelId})
WHERE n.type IN ['DATE','DATERANGE','RELATIVE','NOW','OPEN','UNKNOWN']
  AND (n.canonicalName IS NULL OR n.canonicalName = 'None' OR n.canonicalName = '')
SET n.canonicalName = coalesce(n.expr, n.name, '未知时间')
RETURN count(n) AS c
""")
b_cnt = r[0]["c"]
print(f"\n[B 锚点修复] canonicalName=None → expr/name 回填: {b_cnt} 个")

# 顺便把 DATE 节点的 name 也补了（前端展示用）
run("""
MATCH (n {modelId: $modelId})
WHERE n.type IN ['DATE','DATERANGE','RELATIVE'] AND (n.name IS NULL OR n.name = '')
SET n.name = coalesce(n.canonicalName, n.expr, '时间锚点')
""")

# ========== 修复后快照 ==========
after_evt = run("""
MATCH (n {modelId: $modelId}) WHERE n.type STARTS WITH '事件-' RETURN count(n) AS c
""")[0]["c"]
after_evt_list = run("""
MATCH (n {modelId: $modelId}) WHERE n.type STARTS WITH '事件-'
RETURN n.canonicalName AS name, n.type AS type ORDER BY n.type
""")
after_date_null2 = run("""
MATCH (n {modelId: $modelId})
WHERE (n.type IN ['DATE','DATERANGE','RELATIVE']) AND (n.canonicalName IS NULL OR n.canonicalName = 'None')
RETURN count(n) AS c
""")[0]["c"]

# 图连通性重算
iso_after = run("""
MATCH (n {modelId: $modelId})
WHERE NOT (n)-[:RELATION|CAUSES]-({modelId: $modelId})
RETURN count(n) AS c
""")[0]["c"]
total_nodes = run("MATCH (n {modelId: $modelId}) RETURN count(n) AS c")[0]["c"]
total_rel = run("MATCH ()-[r:RELATION {modelId: $modelId}]->() RETURN count(r) AS c")[0]["c"]
total_causes = run("MATCH ()-[r:CAUSES {modelId: $modelId}]->() RETURN count(r) AS c")[0]["c"]

print("\n" + "=" * 70)
print("  [修复后结果]")
print("=" * 70)
print(f"  严格事件实体(事件-*): {before_evt} → {after_evt}  (目标≥7)  {'✅ 达标' if after_evt >= 7 else '⚠️ 未达'}")
print(f"  锚点 canonicalName=None: {before_date_null} → {after_date_null2}")
print(f"  孤立节点: {iso_after}/{total_nodes} = {round(iso_after/total_nodes*100,1) if total_nodes else 0}%")
print(f"  平均度: {round((total_rel*2 + total_causes*2)/total_nodes,2) if total_nodes else 0}")

if after_evt_list:
    print("\n  【修复后的严格事件列表】")
    for e in after_evt_list:
        print(f"    ✅ {e['name']}  [type: {e['type']}]")

driver.close()
print("\n[完成] 数据修复已提交到 Neo4j")
