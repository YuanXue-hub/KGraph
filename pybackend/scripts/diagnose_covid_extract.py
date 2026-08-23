"""诊断脚本 v2：复用 extraction.py 主流程，对疫情文本做完整抽取，然后对照原文逐项检查。

临时 modelId=888，不污染测试项目003。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
BASE_DIR = str(Path(__file__).resolve().parents[1])
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

from core.llm_client import LLMClient  # noqa: E402
from core.graph_writer import GraphWriter  # noqa: E402
from api.extraction import extract  # noqa: E402
from models.schemas import ExtractionRequest  # noqa: E402

COVID_TEXT = """2026年10月12日，武汉市金银潭医院接诊了三例来自华南海鲜市场的聚集性不明原因肺炎病例，患者均出现发热、干咳及肺部影像学异常。10月14日，湖北省疾控中心启动应急响应，派出专家组赴武汉开展流行病学调查和环境采样。10月15日，武汉市卫健委发布通报，称已排除流感、禽流感、SARS等已知病原体，初步判定为一种新型病毒。10月16日，中国疾控中心（CDC）将病毒样本送至国家病毒资源库进行基因测序。10月17日，国家卫健委宣布成立由钟南山院士领衔的高级别专家组，指导疫情防控和溯源工作。10月18日，华南海鲜市场宣布休市，进行环境卫生整治和消杀。10月19日，基因测序结果显示该病毒与已知冠状病毒的同源性约为79%，初步命名为'COVID-X'。10月20日，武汉市疫情防控指挥部发布通告，要求全市公共场所实施体温检测和健康码查验，并建议市民佩戴口罩。10月22日，世界卫生组织（WHO）发布声明，表示将与中国政府合作调查疫情源头，并呼吁各国加强监测和防控准备。受疫情影响，A股生物医药板块在10月15日至20日期间整体上涨12.5%，其中疫苗概念股'康泰生物'累计涨幅达18.3%。国家药监局于10月21日宣布启动COVID-X疫苗的应急审批绿色通道，并联合多家科研机构成立疫苗攻关小组。"""

DEMO_MODEL_ID = 888
DEMO_DOC_ID = "covid_diagnosis_v1"

# 人工对照清单：原文里应该能抽出来的关键实体/关系/因果
KEY_ENTITIES_EXPECTED = [
    # 机构
    ("武汉市金银潭医院", "机构/医院"),
    ("华南海鲜市场", "机构/市场"),
    ("湖北省疾控中心", "机构/政府"),
    ("武汉市卫健委", "机构/政府"),
    ("中国疾控中心", "机构/政府"),
    ("国家病毒资源库", "机构/科研"),
    ("国家卫健委", "机构/政府"),
    ("世界卫生组织", "机构/国际组织"),
    ("国家药监局", "机构/政府"),
    ("武汉市疫情防控指挥部", "机构/临时"),
    # 人物
    ("钟南山", "人物/专家"),
    # 病原体/疾病/症状
    ("COVID-X", "病原体/病毒"),
    ("流感", "病原体/病毒"),
    ("禽流感", "病原体/病毒"),
    ("SARS", "病原体/病毒"),
    ("不明原因肺炎", "疾病"),
    ("发热", "症状"),
    ("干咳", "症状"),
    # 市场/企业
    ("A股生物医药板块", "市场/板块"),
    ("康泰生物", "企业/上市公司"),
    # 组织/政策
    ("高级别专家组", "组织/临时"),
    ("疫苗攻关小组", "组织/临时"),
    ("应急审批绿色通道", "政策/措施"),
]

KEY_RELATIONS_EXPECTED_HINT = [
    # （头实体, 关系谓词关键词, 尾实体）—— 不必完全相同，按语义命中即可
    ("武汉市金银潭医院", "接诊", "肺炎病例"),
    ("武汉市卫健委", "排除", "流感|禽流感|SARS"),
    ("中国疾控中心", "送至|测序", "国家病毒资源库|基因测序"),
    ("国家卫健委", "成立|领衔", "高级别专家组|钟南山"),
    ("华南海鲜市场", "休市|消杀", "休市"),
    ("钟南山", "领衔", "高级别专家组"),
    ("病毒", "命名为|COVID-X", "COVID-X"),
    ("武汉市疫情防控指挥部", "要求|建议", "体温检测|佩戴口罩"),
    ("世界卫生组织", "合作|呼吁", "中国政府|防控准备"),
    ("疫情", "影响|上涨", "A股生物医药板块"),
    ("康泰生物", "涨幅", "18.3%"),
    ("国家药监局", "启动|成立", "绿色通道|疫苗攻关小组"),
]

KEY_NEGATED_HINT = ["排除.*流感", "排除.*禽流感", "排除.*SARS"]

KEY_CAUSAL_HINT = [
    # 应该至少抽出来的因果关系
    ("疫情", "上涨", "生物医药板块"),
    ("疫情", "影响", "康泰生物.*涨幅"),
    ("休市", "消杀", "整治"),  # 可能抽成因果，也可能是普通关系
    ("接诊病例", "启动", "应急响应"),
]


def _hits_hint(entity_name: str, relation_pred: str, tail: str,
               head: str, pred: str, obj: str) -> bool:
    low = lambda s: s.lower()
    return (low(head) in low(entity_name) or low(entity_name) in low(head)) \
        and (low(pred) in low(relation_pred) or low(relation_pred) in low(pred)) \
        and (low(obj) in low(tail) or low(tail) in low(obj))


def main() -> int:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
    # 强制 deepseek-chat（比 v4-flash 更稳的结构化输出）
    default_model = config["model"].get("model_name", "")
    prefer = os.environ.get("KG_E2E_MODEL", "deepseek-chat")
    if prefer != default_model:
        print(f"💡 临时切换 LLM: {default_model} → {prefer}（脚本内，不改 config.json）")
        config["model"]["model_name"] = prefer
    config["model"].setdefault("timeout_sec", 240)
    config["model"].setdefault("max_retries", 1)

    llm_client = LLMClient(config)
    gw = GraphWriter(config)

    print("=" * 64)
    print("[0/4] 清空 modelId=888 临时数据")
    with gw.driver.session() as s:
        s.run("MATCH (n {modelId:888}) DETACH DELETE n")
        s.run("MATCH (a:TimeAnchor {modelId:888}) DELETE a")

    req = ExtractionRequest(
        text=COVID_TEXT,
        ontology={
            "entityTypes": ["机构", "人物", "政策/措施", "事件", "市场/板块",
                            "企业", "病原体", "症状", "疾病", "药物/疫苗"],
            "relationPredicates": ["接诊", "排除", "启动", "派出", "发布", "送至",
                                   "成立", "指导", "休市", "命名为", "要求", "建议",
                                   "合作", "呼吁", "上涨", "累计涨幅达", "联合",
                                   "领衔", "开展", "进行", "宣布"],
        },
        modelId=DEMO_MODEL_ID,
        mode="llm_two_stage",
        docId=DEMO_DOC_ID,
    )
    app_state = SimpleNamespace(llm_client=llm_client, graph_writer=gw)
    fake_request = SimpleNamespace(app=SimpleNamespace(state=app_state))

    print("\n[1/4] 执行 extract() 全流程（T1 + 校验 + T2 + 校验 + 写库）")
    t0 = time.time()
    try:
        result = extract(req, fake_request)  # type: ignore
    except Exception:
        print("❌ extract() 抛异常：")
        import traceback
        traceback.print_exc()
        gw.close()
        return 1
    dur = int(time.time() - t0)

    print(f"      耗时: {dur}s, token: {result.tokenConsumed}")
    print(f"      实体 {len(result.entities)}, 时间锚点 {len(result.timeAnchors)}, "
          f"关系 {len(result.relations)}, 因果边 {len(result.causalEdges)}")
    print(f"      写库计数: {json.dumps(result.writeCount, ensure_ascii=False)}")

    # 关系按 status 统计
    status_cnt: dict = {}
    for r in result.relations:
        s = r.get("status", "UNKNOWN")
        status_cnt[s] = status_cnt.get(s, 0) + 1
    print(f"      关系分状态: {status_cnt}")

    # ============ 关键实体命中率 ============
    print("\n[2/4] 关键实体命中率（人工对照原文）")
    entity_names = {e.get("canonicalName") or e.get("name") or "" for e in result.entities}
    entity_types = {}
    for e in result.entities:
        k = e.get("canonicalName") or e.get("name") or ""
        entity_types[k] = e.get("type", "")
    hit_e = 0
    miss_e: list = []
    for cname, ctype in KEY_ENTITIES_EXPECTED:
        # 模糊匹配：候选实体名里包含 cname，或者 cname 包含候选实体名
        matched = None
        for en in entity_names:
            if not en:
                continue
            if cname in en or en in cname:
                matched = en
                break
        if matched:
            hit_e += 1
            print(f"   ✅ {cname} <期望类型: {ctype}> → 命中 <{entity_types.get(matched, '?')}>: {matched}")
        else:
            miss_e.append((cname, ctype))
            print(f"   ❌ {cname} <期望类型: {ctype}> → 未命中")
    print(f"\n   关键实体命中率: {hit_e}/{len(KEY_ENTITIES_EXPECTED)} = {hit_e*100//len(KEY_ENTITIES_EXPECTED)}%")

    # ============ 关键关系/否定关系命中率 ============
    print("\n[3/4] 关键关系 & NEGATED 命中率")
    # 否定关系单独统计
    neg_cnt = 0
    for r in result.relations:
        if r.get("status") != "NEGATED":
            continue
        neg_cnt += 1
        print(f"   [NEGATED] ({r.get('head') or r.get('subject')})-"
              f"[{r.get('relation') or r.get('predicate')}]->"
              f"({r.get('tail') or r.get('object')})")
    print(f"   共 {neg_cnt} 条 NEGATED（原文有至少 3 条：排除流感/禽流感/SARS）")

    # 关键关系模糊匹配
    relation_triples = []
    for r in result.relations:
        h = r.get("head") or r.get("subject") or ""
        p = r.get("relation") or r.get("predicate") or ""
        t = r.get("tail") or r.get("object") or ""
        relation_triples.append((h, p, t))
    hit_r = 0
    miss_r: list = []
    for hint_h, hint_p, hint_t in KEY_RELATIONS_EXPECTED_HINT:
        matched = None
        for h, p, t in relation_triples:
            if (hint_h in h or h in hint_h) and (hint_t in t or t in hint_t):
                # 谓词用 | 分隔多关键词，命中一个即可
                preds = [x for x in hint_p.split("|") if x]
                if any(x in p for x in preds):
                    matched = (h, p, t)
                    break
        if matched:
            hit_r += 1
            print(f"   ✅ 期望({hint_h}, {hint_p}, {hint_t}) → 实际: ({matched[0]}, {matched[1]}, {matched[2]})")
        else:
            miss_r.append((hint_h, hint_p, hint_t))
            print(f"   ❌ 期望({hint_h}, {hint_p}, {hint_t}) → 未命中")
    print(f"   关键关系命中率: {hit_r}/{len(KEY_RELATIONS_EXPECTED_HINT)} = "
          f"{hit_r*100//len(KEY_RELATIONS_EXPECTED_HINT)}%")

    # ============ 因果边质量 ============
    print("\n[4/4] 因果边质量")
    if not result.causalEdges:
        print("   ❌ 一条因果边都没产出！")
    else:
        for c in result.causalEdges:
            mark_dir = "🟠" if c.get("direction") == "PREVENT" else "🟢"
            low = " ⚠️lowConf" if c.get("lowConfidence") else ""
            print(f"   {mark_dir}[{c.get('direction')}] sig={c.get('signalWord')!r}: "
                  f"{c.get('causeEvent')} → {c.get('effectEvent')}"
                  f"  conf={c.get('confidence')}, vt_order={c.get('vt_order')}{low}")

    # ============ 质量问题明细（DROPPED/ERROR 是硬伤，WARNING可能只是span修正）============
    print("\n" + "=" * 64)
    print("📋 质量问题分级明细（只看 DROPPED 才是真正丢了东西）")
    from collections import Counter
    lvl_cnt = Counter(q.get("level", "?") for q in result.qualityReport)
    code_cnt = Counter(q.get("code", "?") for q in result.qualityReport)
    print(f"按级别: {dict(lvl_cnt)}")
    print(f"按code Top10: {code_cnt.most_common(10)}")
    dropped = [q for q in result.qualityReport if q.get("level") == "DROPPED"]
    if dropped:
        print(f"\n❗ DROPPED 共 {len(dropped)} 条（这些是被校验墙硬丢弃的，直接影响数量）：")
        for i, q in enumerate(dropped[:20], 1):
            print(f"   {i}. [{q.get('code')}] {q.get('message', '')[:160]}")
    else:
        print("✅ 无 DROPPED，校验墙没有硬丢任何东西")

    gw.close()
    print("\n" + "=" * 64)
    print("✅ 诊断完成，根据上面的命中率和问题清单定位具体根因")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
