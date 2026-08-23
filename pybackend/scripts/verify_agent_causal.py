"""快速验证：agent_tools 查询因果边能力（不重跑LLM，直接用已写入的modelId=999数据）"""
from __future__ import annotations
import json, os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
BASE_DIR = str(Path(__file__).resolve().parents[1])
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

from core import agent_tools

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

agent_tools._Neo4jToolContext.init(config)
DEMO_MODEL_ID = 999

print("=" * 56)
print("1) get_graph_stats(modelId=999) — 应该同时统计普通关系+因果边")
stats = agent_tools.get_graph_stats.func(DEMO_MODEL_ID)
print(stats)

print("\n2) get_entity_relations — 找因果链上的节点")
# 挑选几个确定在因果链中的节点名（从上一步 Neo4j 查询结果里来）
probe_nodes = [
    "新冠疫情的反复",
    "2021年全球大宗商品价格的快速上涨",
    "慢性病长处方政策",
]
for name in probe_nodes:
    print(f"\n  🔍 查询实体: {name}")
    text = agent_tools.get_entity_relations.func(DEMO_MODEL_ID, name, limit=10)
    for line in text.split("\n"):
        print(f"     {line}")
    # 检查因果标记
    has = "[因果]" in text or "[因果·预防]" in text
    print(f"     → 命中因果标记: {'✅ 是' if has else '❌ 否'}")

agent_tools._Neo4jToolContext.close()
print("\n✅ Agent 端验证结束")
