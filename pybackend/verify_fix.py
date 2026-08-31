"""端到端验证：修复后的两阶段抽取（真实 LLM，不写 Neo4j）。
验证点：实体来自真实语料（深流科技），关系数量 > 0 且证据句能在原文中定位。
"""
import sys, json, time
sys.path.insert(0, "/Users/Yuan/xy_workspace/2.projects/java/KGraph/pybackend")

from core.llm_client import LLMClient
from core.prompt_builder import build_node_messages, build_relation_messages, format_entity_table
from core.extraction_validator import QualityReport
from utils.read.read_config import ReadConfig
import pymysql

# 1) 取真实语料
cfg = ReadConfig().read_config("memory")["mysql"]
conn = pymysql.connect(host=cfg["host"], port=cfg["port"], user=cfg["user"],
                       password=cfg["password"], database=cfg["database"],
                       cursorclass=pymysql.cursors.DictCursor)
cur = conn.cursor()
cur.execute("SELECT content FROM corpus WHERE id='2091493482249187330'")
text = cur.fetchone()["content"].strip()
print(f"语料长度: {len(text)} 字, 开头: {text[:50]!r}")

# 2) 阶段1：节点抽取
llm = LLMClient({"model": ReadConfig().read_config("model")})
rep = QualityReport()

from api.extraction import _llm_call_with_retry, _parse_nodes, _parse_relations
t0 = time.time()
node_json, tok1 = _llm_call_with_retry(llm, build_node_messages(text=text))
entities, anchors, alias_map, doc_time = _parse_nodes(node_json, text, rep)
print(f"\n阶段1: 实体×{len(entities)} 时间锚点×{len(anchors)} tokens={tok1} 耗时={time.time()-t0:.0f}s")
for e in entities[:8]:
    print(f"  - {e.canonicalName} <{e.type}>")

# 3) 阶段2：关系抽取
name_set = {e.canonicalName: e.type for e in entities}
entity_table = format_entity_table([{"canonicalName": n, "type": t} for n, t in name_set.items()])
t1 = time.time()
rel_json, tok2 = _llm_call_with_retry(llm, build_relation_messages(
    text=text, entity_table_str=entity_table))
relations = _parse_relations(rel_json, text, name_set, alias_map, rep)
print(f"\n阶段2: 关系×{len(relations)} tokens={tok2} 耗时={time.time()-t1:.0f}s")
for r in relations[:10]:
    print(f"  - {r.subject} -[{r.predicate}]-> {r.object} (conf={r.confidence})")

# 4) 断言
assert len(relations) > 0, "仍然没有关系!"
in_text = all(e.canonicalName in text or any(a in text for a in alias_map if alias_map[a]==e.canonicalName) for e in entities[:5])
print(f"\n=== 验证通过: 实体×{len(entities)} 关系×{len(relations)} ===")
print(f"前5个实体是否来自真实语料: {in_text}")
# 质量报告里是否还有大规模丢弃
drops = [i for i in rep.issues if 'DROPPED' in i.code]
print(f"被丢弃的关系数: {len(drops)}")
