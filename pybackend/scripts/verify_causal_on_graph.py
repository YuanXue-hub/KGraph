"""验证脚本：因果边在图谱上的可见性 + Agent查询能力

三步验证：
1. 清理 modelId=999 旧数据
2. 跑 run_corpus_e2e 重新写入新格式（因果边带 type 属性）
3. 直接连 Neo4j 查因果边的 type/direction 属性，以及模拟 agent_tools 的查询
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
BASE_DIR = str(Path(__file__).resolve().parents[1])
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

from core.graph_writer import GraphWriter  # noqa: E402
from core.llm_client import LLMClient  # noqa: E402
from core import agent_tools  # noqa: E402
from models.schemas import ExtractionRequest  # noqa: E402
from api.extraction import extract  # noqa: E402
from types import SimpleNamespace  # noqa: E402

DEMO_MODEL_ID = 999
CORPUS_PATH = os.path.join(BASE_DIR, "scripts", "corpus_bitemporal_demo.txt")
DEMO_DOC_ID = "corpus_bitemporal_demo_v2"


def main() -> int:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
    config["model"].setdefault("timeout_sec", 180)
    config["model"].setdefault("max_retries", 1)

    gw = GraphWriter(config)
    print("=" * 60)
    print("[1/4] 清理 Neo4j 中 modelId=999 的旧联调数据")
    with gw.driver.session() as s:
        r1 = s.run("MATCH (n {modelId:999}) DETACH DELETE n RETURN count(n) AS c").single()
        r2 = s.run("MATCH (a:TimeAnchor {modelId:999}) DELETE a RETURN count(a) AS c").single()
        print(f"      删除 Entity/CAUSES 节点及关系: {r1['c'] if r1 else 0}")
        print(f"      删除 TimeAnchor: {r2['c'] if r2 else 0}")

    # 临时覆盖 model 为 deepseek-chat（同 run_corpus_e2e）
    default_model = config["model"].get("model_name", "")
    prefer = os.environ.get("KG_E2E_MODEL", "deepseek-chat")
    if prefer and prefer != default_model:
        print(f"      💡  临时切换 LLM: {default_model} → {prefer}")
        config["model"]["model_name"] = prefer

    llm_client = LLMClient(config)

    print("\n[2/4] 重新执行 LLM 抽取（因果边将携带 type 属性）")
    with open(CORPUS_PATH, "r", encoding="utf-8") as f:
        text = f.read().strip()
    req = ExtractionRequest(
        text=text,
        ontology={
            "entityTypes": ["人物", "组织", "职位", "政策", "事件", "企业", "高校", "期刊"],
            "relationPredicates": ["担任", "导致", "推高", "缓解", "避免"],
        },
        modelId=DEMO_MODEL_ID,
        mode="llm_two_stage",
        docId=DEMO_DOC_ID,
    )
    app_state = SimpleNamespace(llm_client=llm_client, graph_writer=gw)
    fake_request = SimpleNamespace(app=SimpleNamespace(state=app_state))
    t0 = time.time()
    result = extract(req, fake_request)  # type: ignore
    print(f"      耗时: {int(time.time()-t0)}s")
    print(f"      entities={len(result.entities)}, relations={len(result.relations)}, "
          f"causalEdges={len(result.causalEdges)}")

    print("\n[3/4] 直接查 Neo4j：因果边的 type 属性是否正确写入（图谱 label 用这个）")
    with gw.driver.session() as s:
        rows = s.run(
            """
            MATCH (ca)-[c:CAUSES {modelId: 999}]->(cb)
            RETURN ca.canonicalName AS cause, cb.canonicalName AS effect,
                   c.type AS edge_type, c.direction AS direction,
                   c.signalWord AS signal_word
            ORDER BY c.createTime DESC
            LIMIT 20
            """
        ).data()

    ok_cnt = 0
    bad_cnt = 0
    for r in rows:
        t = r.get("edge_type") or ""
        # 合格标准：type != "CAUSES"（不是Neo4j关系类型名回退），且非空
        is_ok = bool(t) and t != "CAUSES"
        mark = "✅" if is_ok else "❌"
        if is_ok:
            ok_cnt += 1
        else:
            bad_cnt += 1
        print(f"   {mark} ({r['cause']})-[type={t!r}, dir={r['direction']}, sig={r['signal_word']!r}]->({r['effect']})")
    print(f"\n      图谱label合格: {ok_cnt}, 不合格: {bad_cnt}, 共 {len(rows)} 条因果边")

    print("\n[4/4] 验证 Agent 查询能力（模拟 agent_tools 输出）")
    # 4a) get_graph_stats —— 看是否同时统计普通关系和因果边
    print("  4a) get_graph_stats(modelId=999):")
    agent_tools._init_driver_if_needed(config)  # 确保 agent_tools 有driver
    stats_text = agent_tools.get_graph_stats.func(DEMO_MODEL_ID)
    for line in stats_text.split("\n"):
        print(f"      {line}")

    # 4b) get_entity_relations —— 找一个因果链上的节点（如"大宗商品价格快速上涨"）
    #     先从之前写库的因果边中挑一个 cause 节点名
    probe_node = None
    if rows:
        probe_node = rows[0]["cause"]
    if probe_node:
        print(f"\n  4b) get_entity_relations(modelId=999, name={probe_node!r}):")
        rel_text = agent_tools.get_entity_relations.func(DEMO_MODEL_ID, probe_node, limit=15)
        for line in rel_text.split("\n"):
            print(f"      {line}")
        # 人工检查：输出中是否包含 [因果] 前缀
        has_causal_marker = "[因果]" in rel_text
        print(f"\n      命中因果前缀标记: {'✅ 是' if has_causal_marker else '❌ 否（Agent 仍然看不到因果边！）'}")

    gw.close()
    try:
        agent_tools._DRIVER.close()
    except Exception:
        pass

    print("\n" + "=" * 60)
    print("✅ 验证完成")
    if bad_cnt > 0:
        print(f"⚠️  仍有 {bad_cnt} 条因果边图谱label不正确")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
