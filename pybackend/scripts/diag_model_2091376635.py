"""诊断 model_id=2091376635910582273。"""
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
from neo4j import GraphDatabase

MODEL_ID = 2091376635910582273
cfg = json.load(open(Path(__file__).resolve().parent.parent / "config.json"))["neo4j"]
driver = GraphDatabase.driver(cfg["url"], auth=(cfg["username"], cfg["password"]))

def run(c, **kw):
    with driver.session() as s:
        return [dict(r) for r in s.run(c, modelId=MODEL_ID, **kw)]

def pct(a, b): return "0.0%" if b==0 else f"{a*100/b:.1f}%"

try:
    B = G = R = Y = ""  # disable colors in file
    s = run("""
MATCH (e:Entity {modelId:$modelId}) WITH count(e) AS ents
OPTIONAL MATCH ()-[r:RELATION {modelId:$modelId}]->() WITH ents, count(r) AS rels
OPTIONAL MATCH ()-[c:CAUSES {modelId:$modelId}]->() WITH ents, rels, count(c) AS causes
OPTIONAL MATCH (a:TimeAnchor {modelId:$modelId}) WITH ents, rels, causes, count(a) AS anchors
RETURN ents, rels, causes, anchors""")[0]
    total_ents, total_rels, total_causes, total_anchors = s['ents'], s['rels'], s['causes'], s['anchors']

    ev_rows = run('MATCH (e:Entity {modelId:$modelId}) WHERE e.type STARTS WITH "事件-" RETURN e.canonicalName AS n, e.type AS t, size(coalesce(e.mentions,[])) AS m ORDER BY t, n')
    strict_evs = len(ev_rows)
    loose_ev = run('MATCH (e:Entity {modelId:$modelId}) WHERE (e.type IS NULL OR NOT e.type STARTS WITH "事件-") AND (toString(e.canonicalName) CONTAINS "事件" OR toString(e.type) CONTAINS "事件") RETURN e.canonicalName AS n, e.type AS t LIMIT 20')
    n_loose = len(loose_ev)

    iso = run('MATCH (e:Entity {modelId:$modelId}) OPTIONAL MATCH (e)-[r]-() WHERE type(r) IN ["RELATION","CAUSES"] AND r.modelId=$modelId WITH e, count(r) AS k WHERE k=0 RETURN e.canonicalName AS n, e.type AS t ORDER BY t, n')
    isolated = len(iso)
    degs = run('MATCH (e:Entity {modelId:$modelId}) OPTIONAL MATCH (e)-[r]-() WHERE type(r) IN ["RELATION","CAUSES"] AND r.modelId=$modelId RETURN e.canonicalName AS n, e.type AS t, count(r) AS d ORDER BY d DESC, n ASC')
    deg_lst = [x['d'] for x in degs]
    avg_deg = sum(deg_lst)/len(deg_lst) if deg_lst else 0

    types = run('MATCH (e:Entity {modelId:$modelId}) WITH coalesce(e.type,"NULL") AS t, count(e) AS c RETURN t, c ORDER BY c DESC LIMIT 25')
    pred = run('MATCH ()-[r:RELATION {modelId:$modelId}]->() WITH coalesce(r.relationType, coalesce(r.predicate,"NULL")) AS p, count(r) AS c RETURN p, c ORDER BY c DESC LIMIT 40')
    status = run('MATCH ()-[r:RELATION {modelId:$modelId}]->() WITH coalesce(r.status,"NULL") AS s, count(r) AS c RETURN s, c ORDER BY c DESC')
    neg = run('MATCH (s)-[r:RELATION {modelId:$modelId}]->(o) WHERE r.status="NEGATED" RETURN s.canonicalName AS a, coalesce(r.relationType, r.predicate) AS p, o.canonicalName AS b ORDER BY a,p,b')
    temp = run('MATCH ()-[r:RELATION {modelId:$modelId}]->() WITH count(r) AS tot, sum(CASE WHEN r.vt_from IS NOT NULL OR r.vt_to IS NOT NULL THEN 1 ELSE 0 END) AS has_vt, sum(CASE WHEN r.vt_from IS NOT NULL AND r.vt_to IS NOT NULL THEN 1 ELSE 0 END) AS both RETURN tot, has_vt, both')[0]
    cov = run('MATCH (e:Entity {modelId:$modelId}) WHERE (e)-[:RELATION {modelId:$modelId}]->() OR ()-[:RELATION {modelId:$modelId}]->(e) RETURN count(e) AS c')[0]['c']
    caus = run('MATCH (s)-[c:CAUSES {modelId:$modelId}]->(o) RETURN s.canonicalName AS a, s.type AS at, o.canonicalName AS b, o.type AS bt, c.direction AS d, c.signalWord AS sw')
    aq = run('MATCH (a:TimeAnchor {modelId:$modelId}) OPTIONAL MATCH (a)-[ra]-() WHERE type(ra) IN ["RELATION","CAUSES"] AND ra.modelId=$modelId WITH a, count(ra) AS k WITH count(a) AS tot, sum(CASE WHEN a.canonicalName IS NULL OR a.canonicalName="" THEN 1 ELSE 0 END) AS non_cn, sum(CASE WHEN a.type="DATE" THEN 1 ELSE 0 END) AS dt, sum(CASE WHEN a.type="DATERANGE" THEN 1 ELSE 0 END) AS dr, sum(CASE WHEN a.type="RELATIVE" THEN 1 ELSE 0 END) AS rv, sum(CASE WHEN k=0 THEN 1 ELSE 0 END) AS iso_a RETURN tot, non_cn, dt, dr, rv, iso_a')[0]

    signal_words = ['紧接着','随后','之后','随即','使得','推动','引发','加速','受…影响','受...影响','带动','发布后','同日','推动下','影响下','叠加','启动后','落地后','完成后','上报']
    sig_rels = [row for row in pred if any(w in str(row['p']) for w in signal_words)]

    check_entities = [
        '广州市第八人民医院接诊聚集性发热病例','康泰瑞普生物连续涨停',
        '广州市卫健委排除已知病原体','广东省疾控启动突发公共卫生事件四级应急响应',
        '国家药监局启动应急审批绿色通道','岭南水产批发市场全面休市',
        'CoV-N25疫苗攻关联合体成立','国家卫健委发布诊疗方案',
    ]
    hits = {}
    for name in check_entities:
        rows = run('MATCH (e:Entity {modelId:$modelId}) WHERE e.canonicalName=$name RETURN e.type AS t', name=name)
        hits[name] = (True, rows[0]['t']) if rows else (False, None)

    sep = "=" * 30
    print(f"\n{sep*2}\n  KGraph 质量诊断：modelId={MODEL_ID}\n{sep*2}")
    ev_ok = strict_evs/total_ents>=0.15 if total_ents else False
    iso_ok = total_ents and (isolated/total_ents<=0.10)
    cov_v = cov/total_ents if total_ents else 0
    cov_ok = cov_v>=0.85
    deg_ok = avg_deg>=2.0
    print(f"""
1. 基础指标总览
  实体总数                    : {total_ents}
  时间锚点                    : {total_anchors}
  普通关系[:RELATION]         : {total_rels}
  因果边[:CAUSES]             : {total_causes}（T2废弃预期=0）
  关系/实体比                 : {round(total_rels/total_ents,2) if total_ents else 0} （期望≥1.2）
  严格事件实体(type=事件-*)  : {strict_evs}  | 占比 {pct(strict_evs,total_ents)} | 目标≥15% → {'✅ 达标' if ev_ok else '❌ 未达'}
  宽松不合规事件(待归一化)    : {n_loose} 个
  孤立实体(度数=0)            : {isolated} | 占比 {pct(isolated,total_ents)} | 目标≤10% → {'✅ 达标' if iso_ok else '❌ 未达'}
  实体连至少1条RELATION       : {cov}/{total_ents} = {pct(cov,total_ents)} | 目标≥85% → {'✅ 达标' if cov_ok else '⚠️ 接近' if cov_v>=0.65 else '❌ 低'}
  平均度                      : {avg_deg:.2f} | 目标≥2.0 → {'✅ 达标' if deg_ok else '❌ 未达'}
""")

    print(f"2. 严格事件实体清单（type=事件-*，共{strict_evs}个）")
    if ev_rows:
        cc = Counter(e['t'] for e in ev_rows)
        print(f"  type分布（{len(cc)}种）:", dict(cc.most_common(25)))
        for e in ev_rows: print(f"    · {e['n']} ｜ {e['t']} ｜ mentions={e['m']}")
    else:
        print("  ⚠️  0个")
    if loose_ev:
        print(f"\n  2b.宽松不合规事件({n_loose}个):")
        for e in loose_ev: print(f"    · {e['n']} ｜ 当前type={e['t']}")

    print(f"\n3. 实体type分布Top 20")
    for r in types: print(f"  {r['t']:<24}{r['c']:>3}个 ({pct(r['c'],total_ents)})")

    print(f"\n4. 关系谓词Top 40 + 时态率")
    if total_rels:
        print(f"  vt_from/vt_to 有任一 : {temp['has_vt']}/{temp['tot']} = {pct(temp['has_vt'],temp['tot'])}")
        print(f"  vt_from AND vt_to齐全 : {temp['both']}/{temp['tot']} = {pct(temp['both'],temp['tot'])}")
    print("  谓词频次:")
    for r in pred:
        mark = ' 【承接信号词边】' if any(w in str(r['p']) for w in signal_words) else ''
        print(f"    {r['p']:<22}{r['c']:>3}次{mark}")
    print("  status分布:", {r['s']:r['c'] for r in status})
    if neg:
        print(f"  NEGATED关系（≥{len(neg)}条）:")
        for r in neg: print(f"    {r['a']} --[{r['p']}]→ {r['b']}")

    print(f"\n5. 度数Top 15 HUB / 前15个孤立节点")
    for r in degs[:15]:
        m = ' ⭐HUB' if r['d']>=5 else ''
        print(f"  度={r['d']:<3} {str(r['t'])[:20]:<22} {r['n']}{m}")
    if isolated:
        print(f"  孤立节点({isolated}个，取前15):")
        for r in iso[:15]: print(f"    · {r['n']} ｜ {r['t']}")

    print(f"\n6. 时间锚点质量")
    print(f"  锚点总数       : {aq['tot']}")
    print(f"  canonicalName空: {aq['non_cn']}")
    print(f"  DATE/DATERANGE/RELATIVE : {aq['dt']}/{aq['dr']}/{aq['rv']}")
    iso_a_pct = aq['iso_a']/aq['tot'] if aq['tot'] else 0
    print(f"  孤立锚点(无连边): {aq['iso_a']} ｜ 占比 {pct(aq['iso_a'], aq['tot'])} → {'✅ 良好' if iso_a_pct<=0.2 else '⚠️ 未连边太多'}")

    print(f"\n7. 承接信号词边专项统计（本次新增改进点核心检验）")
    if sig_rels:
        tot_sig = sum(r['c'] for r in sig_rels)
        print(f"  命中承接信号词边 {tot_sig} 条（占全部关系 {pct(tot_sig,total_rels)}）:")
        for r in sig_rels: print(f"    · {r['p']}: {r['c']}次")
    else:
        print("  ⚠️  0 条 —— 事件之间缺少「随后/紧接着/使得/推动/带动」等承接边，逻辑链断环")

    print(f"\n8. 8个关键实体/事件命中检查")
    for n,(ok,t) in hits.items():
        s = f"✅ 命中 type={t}" if ok else "❌ 未命中"
        print(f"  {s} ｜ {n}")

    print(f"\n9. 因果边[:CAUSES]")
    if not caus:
        print("  0条 → T2废弃后符合预期。后续图推理补上。")
    else:
        print(f"  {len(caus)}条:")
        for c in caus[:12]: print(f"    {c['a']}[{c['at']}]--[{c['d']}/{c['sw']}]→{c['b']}[{c['bt']}]")

    scr = {
        '事件覆盖率': min(1, (strict_evs/total_ents)/0.15 if total_ents else 0),
        '孤立≤10%' : max(0, 1 - (isolated/total_ents - 0.10)*10) if total_ents else 0,
        '平均度≥2.0': min(1, avg_deg/2.0),
        '关系覆盖率': min(1, (cov/total_ents)/0.85 if total_ents else 0),
        '时态绑定率': min(1, (temp['both']/total_rels)/0.5 if total_rels else 0),
        '格式正确率': strict_evs/max(1, strict_evs+n_loose),
        '信号词边≥10%': min(1, (sum(r['c'] for r in sig_rels)/total_rels)/0.10 if total_rels else 0),
        '8大关键命中': sum(1 for ok,_ in hits.values() if ok)/len(hits),
    }
    w = {'事件覆盖率':0.15,'孤立≤10%':0.18,'平均度≥2.0':0.12,'关系覆盖率':0.13,'时态绑定率':0.10,'格式正确率':0.12,'信号词边≥10%':0.10,'8大关键命中':0.10}
    total = sum(min(1,max(0,scr[k]))*w[k] for k in w)
    print(f"\n📊 完整性综合评分（8项加权）")
    for k,ww in w.items():
        sc = min(1,max(0,scr[k]))
        mark = '⭐' if sc>=0.9 else ('✅' if sc>=0.7 else ('⚠️' if sc>=0.4 else '❌'))
        print(f"  {mark} {k:<16} {sc*100:5.1f}/100  (权重{ww*100:.0f}%)")
    print(f"\n  🏁 加权总分: {total*100:5.1f}/100\n")
finally:
    driver.close()
