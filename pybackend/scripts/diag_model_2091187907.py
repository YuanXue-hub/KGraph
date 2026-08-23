"""诊断 model_id=2091187907741143042 抽取质量。"""
import json
from neo4j import GraphDatabase

MODEL_ID = 2091187907741143042

with open("config.json") as f:
    cfg = json.load(f)["neo4j"]

driver = GraphDatabase.driver(cfg["url"], auth=(cfg["username"], cfg["password"]))


def run(query, **params):
    with driver.session() as s:
        return list(s.run(query, modelId=MODEL_ID, **params))


print("=" * 80)
print(f"  质量评估报告：model_id = {MODEL_ID}")
print("=" * 80)

# ========== 1. 基础统计 ==========
total_nodes = run("MATCH (n {modelId: $modelId}) RETURN count(n) AS total")[0]["total"]
total_rel = run("MATCH ()-[r:RELATION {modelId: $modelId}]->() RETURN count(r) AS cnt")[0]["cnt"]
total_causes = run("MATCH ()-[r:CAUSES {modelId: $modelId}]->() RETURN count(r) AS cnt")[0]["cnt"]

print(f"\n📊 一、基础统计")
print(f"  实体总数:           {total_nodes}")
print(f"  普通关系[:RELATION]: {total_rel}")
print(f"  因果边[:CAUSES]:     {total_causes}")
print(f"  关系/实体比:         {round((total_rel + total_causes) / total_nodes, 2) if total_nodes else 0}  (期望≥1.5)")

# ========== 2. 事件实体分析（核心指标） ==========
print(f"\n📋 二、事件实体分析（核心质量指标）")

# 2.1 严格：type以"事件-"开头
events_strict = run("""
MATCH (n {modelId: $modelId}) 
WHERE n.type STARTS WITH '事件-' 
RETURN n.canonicalName AS name, n.type AS type
ORDER BY n.type
""")
evt_strict_cnt = len(events_strict)

# 2.2 宽松：任何包含"事件"字样的type
events_loose = run("""
MATCH (n {modelId: $modelId}) 
WHERE toLower(n.type) CONTAINS '事件' OR toLower(n.type) CONTAINS '涨停' OR toLower(n.type) CONTAINS '异动' OR toLower(n.type) CONTAINS '休市' OR toLower(n.type) CONTAINS '接诊' OR toLower(n.type) CONTAINS '发布' OR toLower(n.type) CONTAINS '测序' OR toLower(n.type) CONTAINS '排查'
RETURN n.canonicalName AS name, n.type AS type
ORDER BY n.type
""")
evt_loose_cnt = len(events_loose)

evt_target = max(7, int(total_nodes * 0.15))  # 至少7个或15%

print(f"  事件实体（严格type=事件-*）:  {evt_strict_cnt}  ({round(evt_strict_cnt/total_nodes*100,1)}%)  目标≥{evt_target}个  →  {'✅ 达标' if evt_strict_cnt >= evt_target else '❌ 不足'}")
print(f"  事件实体（宽松含事件字样）:    {evt_loose_cnt}  ({round(evt_loose_cnt/total_nodes*100,1)}%)")

if events_strict:
    print(f"\n  【严格事件列表】（type以'事件-'开头，格式合规可直接被Agent检索）")
    for e in events_strict:
        print(f"    ✅ {e['name']}  [type: {e['type']}]")
else:
    print(f"\n  ⚠️  0个严格格式事件实体！Agent将无法触发get_causal_chain")

if events_loose and not events_strict:
    print(f"\n  【宽松事件列表】（格式不合规，Agent看不到）——需要修复Prompt或抽取流程：")
    for e in events_loose:
        print(f"    ❌ {e['name']}  [type: {e['type']}]  (缺少'事件-'前缀)")

# ========== 3. 实体type分布 ==========
print(f"\n🏷️  三、实体type分布（Top 20）")
type_dist = run("""
MATCH (n {modelId: $modelId}) 
RETURN coalesce(n.type, 'NULL') AS tp, count(*) AS cnt
ORDER BY cnt DESC LIMIT 20
""")
for r in type_dist:
    bar = "█" * min(r["cnt"], 40)
    print(f"  {r['cnt']:>3}  {r['tp']:<30} {bar}")

# ========== 4. 因果边详情 ==========
print(f"\n🔗 四、因果边[:CAUSES]详情（目标≥10条）")
causes = run("""
MATCH (a)-[c:CAUSES {modelId: $modelId}]->(b)
RETURN a.canonicalName AS a_name, coalesce(a.type, 'NULL') AS a_type,
       coalesce(c.direction, '?') AS dir, coalesce(c.signalWord, '') AS sig,
       coalesce(c.confidence, 0) AS conf,
       b.canonicalName AS b_name, coalesce(b.type, 'NULL') AS b_type
""")
print(f"  因果边总数: {len(causes)}  →  {'✅ ≥10条' if len(causes) >= 10 else '❌ <10条'}")
if causes:
    for i, r in enumerate(causes, 1):
        tag = f"[因果{r['dir']}]" if r['dir'] else "[因果]"
        a_evt = "✅" if str(r["a_type"]).startswith("事件-") else "❌"
        b_evt = "✅" if str(r["b_type"]).startswith("事件-") else "❌"
        print(f"  {i:>2}. {a_evt} {r['a_name']}({r['a_type']}) --{tag}('{r['sig']}', c={r['conf']:.2f})-> {b_evt} {r['b_name']}({r['b_type']})")
    # 统计因果两端事件合规率
    ends_ok = sum(1 for r in causes if str(r["a_type"]).startswith("事件-") and str(r["b_type"]).startswith("事件-"))
    rate = round(ends_ok / len(causes) * 100, 0) if causes else 0
    print(f"\n  因果两端均为严格事件实体(事件-*): {ends_ok}/{len(causes)} = {rate:.0f}%  (目标≥90%)")
else:
    print(f"  ⚠️  图谱中没有因果边！T2抽取可能失败或信号词不足")

# ========== 5. 图连通性 ==========
print(f"\n🌐 五、图连通性（离散点分析）")
iso = run("""
MATCH (n {modelId: $modelId})
WHERE NOT (n)-[:RELATION|CAUSES]-({modelId: $modelId})
RETURN count(n) AS cnt
""")[0]["cnt"]
iso_rate = round(iso/total_nodes*100, 1) if total_nodes else 0
avg_degree = (total_rel*2 + total_causes*2) / total_nodes if total_nodes else 0

print(f"  孤立节点（度=0）: {iso}  ({iso_rate}%)  →  {'✅ ≤10%' if iso_rate <= 10 else '❌ >10%，离散点多'}")
print(f"  平均度:         {avg_degree:.2f}  →  {'✅ ≥2.0' if avg_degree >= 2.0 else '❌ <2.0，网络稀疏'}")

if iso > 0:
    print(f"\n  前20个孤立节点示例:")
    iso_nodes = run("""
    MATCH (n {modelId: $modelId})
    WHERE NOT (n)-[:RELATION|CAUSES]-({modelId: $modelId})
    RETURN n.canonicalName AS name, n.type AS type LIMIT 20
    """)
    for n in iso_nodes:
        print(f"    ⚪ {n['name']}  [{n['type']}]")

# ========== 6. 关键事件关键词搜索 ==========
print(f"\n🔍 六、关键事件关键词匹配（用户问题场景专项验证）")
keywords = [
    ("接诊病例", "接诊"),
    ("应急响应", "应急"),
    ("发布会/发布通报", "发布"),
    ("休市/消杀", "休市"),
    ("基因测序", "测序"),
    ("板块异动/上涨", "板块"),
    ("个股涨停/康泰瑞普涨停", "涨停"),
    ("疫苗绿色通道", "绿色通道"),
    ("攻关小组成立", "攻关"),
    ("NEGATED关系/排除病原体", "排除"),
]
for label, kw in keywords:
    results = run("""
    MATCH (n {modelId: $modelId})
    WHERE n.canonicalName CONTAINS $kw OR coalesce(n.name, '') CONTAINS $kw OR coalesce(n.type, '') CONTAINS $kw
    RETURN n.canonicalName AS name, n.type AS type
    LIMIT 5
    """, kw=kw)
    status = "✅" if results else "❌"
    print(f"  {status} {label}: 找到{len(results)}个")
    for r in results:
        evt_ok = "✅事件格式" if str(r["type"]).startswith("事件-") else "⚠️ 格式待修"
        print(f"       -> {r['name']}  [type: {r['type']}] {evt_ok}")

# ========== 7. 关键静态实体检查 ==========
print(f"\n🏢 七、关键静态实体检查")
static_checks = [
    "广州市第八人民医院", "康泰瑞普生物", "岭南水产", "广东省疾病预防控制中心",
    "广州市卫生健康委员会", "国家药品监督管理局", "COVID-N25", "疫苗攻关联合体",
    "达瑞生物科技", "广药新生命", "国家卫生健康委员会", "广州市第八医院",
    "康泰瑞普", "广药新生命", "联防联控",
]
found = 0
for name in static_checks:
    results = run("""
    MATCH (n {modelId: $modelId})
    WHERE n.canonicalName = $name OR coalesce(n.name, '') = $name 
       OR n.canonicalName CONTAINS $name OR coalesce(n.name, '') CONTAINS $name
    RETURN n.canonicalName AS name, n.type AS type
    LIMIT 3
    """, name=name)
    if results:
        found += 1
        print(f"  ✅ {name}:")
        for r in results:
            print(f"       -> {r['name']}  [type: {r['type']}]")
    else:
        print(f"  ❌ {name}: 未找到")
print(f"\n  静态实体覆盖率: {found}/{len(static_checks)}")

# ========== 8. NEGATED关系检查 ==========
print(f"\n🚫 八、NEGATED关系（排除病原体）")
negated = run("""
MATCH ()-[r:RELATION {modelId: $modelId, status: 'NEGATED'}]->()
RETURN startNode(r).canonicalName AS s, r.predicate AS p, endNode(r).canonicalName AS o,
       coalesce(r.status, '') AS status
""")
print(f"  NEGATED关系数: {len(negated)}  (期望≥4条：排除流感/禽流感/SARS/MERS等)")
for r in negated:
    print(f"    ❌ {r['s']} --[{r['p']}]--> {r['o']}  (status={r['status']})")

driver.close()
print("\n" + "=" * 80)
print("  评估结束")
print("=" * 80)
