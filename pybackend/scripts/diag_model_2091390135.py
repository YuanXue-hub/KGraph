#!/usr/bin/env python3
"""诊断 model_id=2091390135340920833 的抽取质量（直通模式）"""
import json
import sys
from collections import Counter, defaultdict

sys.path.insert(0, '/Users/Yuan/xy_workspace/2.projects/java/KGraph/pybackend')
from neo4j import GraphDatabase

MODEL_ID = 2091390135340920833
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PWD = "demodemo"

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PWD))


def q(cypher, **kwargs):
    with driver.session() as s:
        return list(s.run(cypher, modelId=MODEL_ID, **kwargs))


# 1. 基础计数
print("=" * 70)
print(f"📊 模型 {MODEL_ID} 抽取质量诊断报告（直通模式）")
print("=" * 70)

# 查 MySQL 里的原始文本
import pymysql
conn = pymysql.connect(host='localhost', port=3306, user='root',
                       password='123456', database='seedboot', charset='utf8mb4')
cur = conn.cursor()
cur.execute("SELECT modelName FROM graph_model WHERE id=%s", (MODEL_ID,))
r = cur.fetchone()
print(f"\n模型名称: {r[0] if r else '未知'}")

# 找 extraction_task 里的原文
cur.execute("""
    SELECT id, inputText, corpusId, createTime, status, tokenConsumed, duration, result
    FROM extraction_task
    WHERE modelId=%s AND extractionType='LLM' ORDER BY id DESC LIMIT 1
""", (MODEL_ID,))
task = cur.fetchone()
TASK_RESULT = None
if task:
    tid, text, did, ct, st, tok, dur, rslt = task
    TASK_RESULT = rslt
    print(f"抽取任务ID: {tid}, 语料ID: {did}, 创建时间: {ct}, 状态: {st}")
    print(f"Token消耗: {tok}, 耗时: {dur}ms")
    print(f"输入文本长度: {len(text) if text else 0} 字符")
    if text:
        print(f"文本前200字: {text[:200]}…")
else:
    text = ""
    print("⚠️  未找到 extraction_task 记录")
conn.close()

# 2. Neo4j 节点与关系计数
print("\n" + "-" * 50)
print("🔢  基础计数")
print("-" * 50)

total_nodes = q("MATCH (n) WHERE n.modelId=$modelId RETURN count(n) AS c")[0]["c"]
total_rels = q("""
    MATCH ()-[r]->() WHERE r.modelId=$modelId RETURN count(r) AS c
""")[0]["c"]
causal_rels = q("""
    MATCH ()-[r:CAUSES]->() WHERE r.modelId=$modelId RETURN count(r) AS c
""")[0]["c"]
normal_rels = q("""
    MATCH ()-[r:RELATION]->() WHERE r.modelId=$modelId RETURN count(r) AS c
""")[0]["c"]
anchor_nodes = q("""
    MATCH (n:TimeAnchor) WHERE n.modelId=$modelId RETURN count(n) AS c
""")[0]["c"]

# 节点按标签分类
label_rows = q("""
    MATCH (n) WHERE n.modelId=$modelId
    WITH labels(n) AS lbls, count(n) AS cnt
    RETURN lbls, cnt ORDER BY cnt DESC
""")
print(f"\n节点总数: {total_nodes}")
print(f"  时间锚点: {anchor_nodes}")
print(f"  其他节点: {total_nodes - anchor_nodes}")
for r in label_rows:
    print(f"    标签{tuple(r['lbls'])} × {r['cnt']}")

print(f"\n关系总数: {total_rels}")
print(f"  [:RELATION] 普通关系: {normal_rels}")
print(f"  [:CAUSES] 因果边:    {causal_rels}")

# 3. 实体/事件类型分布
print("\n" + "-" * 50)
print("🏷  实体类型分布")
print("-" * 50)

type_rows = q("""
    MATCH (n) WHERE n.modelId=$modelId AND NOT 'TimeAnchor' IN labels(n)
    AND n.type IS NOT NULL
    RETURN coalesce(n.type, '无type') AS t, count(n) AS cnt
    ORDER BY cnt DESC LIMIT 20
""")
type_counter = Counter({r["t"]: r["cnt"] for r in type_rows})
ev_types = {t: c for t, c in type_counter.items() if str(t).startswith("事件") or str(t).startswith("事件-")}
event_count = sum(ev_types.values())
non_event_count = total_nodes - anchor_nodes - event_count

print(f"\n实体（非锚点）: {total_nodes - anchor_nodes}")
print(f"  事件实体: {event_count}  ({event_count / max(1, total_nodes - anchor_nodes):.1%})")
if ev_types:
    print(f"  事件类型分布:")
    for t, c in sorted(ev_types.items(), key=lambda x: -x[1]):
        print(f"    - {t}: {c}")
print(f"  静态实体: {non_event_count}")
print(f"\n  TOP 15 实体类型:")
for t, c in list(type_counter.items())[:15]:
    bar = "█" * min(40, c * 2)
    print(f"    {t:<30} ×{c:<4} {bar}")

# 4. 关系谓词分布
print("\n" + "-" * 50)
print("🔗  关系类型 (predicate) 分布")
print("-" * 50)

pred_rows = q("""
    MATCH ()-[r:RELATION]->() WHERE r.modelId=$modelId AND r.relationType IS NOT NULL
    RETURN coalesce(r.relationType, r.type, '未知') AS pred, count(r) AS cnt
    ORDER BY cnt DESC LIMIT 20
""")
print(f"\n  TOP 15 关系谓词:")
for r in pred_rows[:15]:
    bar = "█" * min(40, r["cnt"] * 2)
    print(f"    {r['pred']:<30} ×{r['cnt']:<4} {bar}")

# 因果边 signalWord
if causal_rels > 0:
    sig_rows = q("""
        MATCH ()-[r:CAUSES]->() WHERE r.modelId=$modelId
        RETURN coalesce(r.signalWord, r.type, '未知') AS sw, count(r) AS cnt
        ORDER BY cnt DESC
    """)
    print(f"\n  因果边 signalWord 分布:")
    for r in sig_rows:
        print(f"    {r['sw']}: {r['cnt']}")

# 5. 孤立节点 / 度分布
print("\n" + "-" * 50)
print("🕸  网络拓扑指标")
print("-" * 50)

degree_rows = q("""
    MATCH (n) WHERE n.modelId=$modelId
    OPTIONAL MATCH (n)-[r]-() WHERE r.modelId=$modelId
    WITH n, count(r) AS d
    RETURN d, count(n) AS cnt ORDER BY d
""")
deg_dist = {r["d"]: r["cnt"] for r in degree_rows}
isolated = deg_dist.get(0, 0)
sum_d = sum(d * c for d, c in deg_dist.items())
avg_deg = sum_d / max(1, total_nodes)
max_deg = max(deg_dist.keys()) if deg_dist else 0

print(f"\n孤立节点 (度=0): {isolated} / {total_nodes} ({isolated / max(1, total_nodes):.1%})")
print(f"平均度: {avg_deg:.2f}")
print(f"最大度: {max_deg}")
print(f"度分布 (度×节点数):")
for d in sorted(deg_dist.keys()):
    if d <= 6 or d == max_deg:
        print(f"  {d}: {'█' * min(50, deg_dist[d])} ({deg_dist[d]})")
    elif d == 7:
        print(f"  ... (省略 d≥7)")

# 6. 详细抽样：事件实体列表 + 因果边列表
print("\n" + "-" * 50)
print("📋  事件实体抽样（前20条）")
print("-" * 50)
event_samples = q("""
    MATCH (n) WHERE n.modelId=$modelId AND NOT 'TimeAnchor' IN labels(n)
    AND (toString(n.type) STARTS WITH '事件')
    RETURN coalesce(n.name, n.canonicalName, n.mention, '?') AS nm, n.type AS tp
    LIMIT 20
""")
if event_samples:
    for r in event_samples:
        print(f"  [{r['tp']}] {r['nm']}")
else:
    print("  ⚠️  未识别到事件实体（type 不以'事件'开头），展示 type 包含'事件'关键字:")
    alt = q("""
        MATCH (n) WHERE n.modelId=$modelId AND NOT 'TimeAnchor' IN labels(n)
        AND toString(n.type) CONTAINS '事件'
        RETURN coalesce(n.name, n.canonicalName, n.mention, '?') AS nm, n.type AS tp LIMIT 20
    """)
    if alt:
        for r in alt:
            print(f"  [{r['tp']}] {r['nm']}")
    else:
        print("  ❌ 完全没有事件实体")

# 抽样节点名称列表（前 15 个所有节点）
print("\n" + "-" * 50)
print("👀  全部节点名称抽样 (前30)")
print("-" * 50)
all_nodes = q("""
    MATCH (n) WHERE n.modelId=$modelId
    RETURN coalesce(n.name, n.canonicalName, n.mention, toString(id(n))) AS nm,
           labels(n) AS lbls, n.type AS tp
    LIMIT 30
""")
for r in all_nodes:
    lbl = '/'.join(r['lbls'])
    print(f"  [{lbl}|{r['tp'] or '无type'}] {r['nm']}")

# 因果边抽样
print("\n" + "-" * 50)
print("🔗  因果边抽样 ([:CAUSES])")
print("-" * 50)
if causal_rels > 0:
    cause_samples = q("""
        MATCH (a)-[r:CAUSES]->(b) WHERE r.modelId=$modelId
        RETURN coalesce(a.name, a.canonicalName, a.mention, '?') AS src,
               coalesce(b.name, b.canonicalName, b.mention, '?') AS dst,
               r.direction AS dir, r.signalWord AS sw, r.confidence AS conf
        LIMIT 20
    """)
    for r in cause_samples:
        print(f"  {r['src']} --[{r['sw'] or r['dir']} ({r['conf']:.2f})]--> {r['dst']}")
else:
    print("  ⚠️  无 [:CAUSES] 因果边")

# 7. 质量报告（extraction_task 返回的 result）
print("\n" + "-" * 50)
print("🧾  抽取任务结果 (extraction_task.result)")
print("-" * 50)
if TASK_RESULT:
    try:
        rdata = json.loads(TASK_RESULT) if isinstance(TASK_RESULT, str) else TASK_RESULT
        qr = rdata.get('qualityReport') or rdata.get('quality_report') or []
        print(f"Token消耗: {rdata.get('tokenConsumed') or task[5] if task else '?'}, "
              f"写入计数: {rdata.get('writeCount') or '?'}")
        print(f"qualityReport 条目数: {len(qr)}")
        for item in qr[:10]:
            lvl = item.get('level', '?')
            code = item.get('code', '?')
            msg = item.get('message', '')[:150]
            print(f"  [{lvl:<7} {code}] {msg}")
    except Exception as e:
        print(f"  result 解析失败: {e}")
        print(f"  原文前300: {str(TASK_RESULT)[:300]}")
else:
    print("  ⚠️  extraction_task.result 为空")

print("\n" + "=" * 70)
print("📝 评估小结（请对照结论）")
print("=" * 70)

driver.close()
