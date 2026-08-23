"""端到端联调脚本：真实语料走完整 LLM 抽取链路。

与 test_llm_extraction_quality.py（纯离线、构造 payload）不同：
  - 真读 corpus_bitemporal_demo.txt 作为输入
  - 真调 LLM（deepseek-v4-flash）跑 T1 + T2
  - 真连 Neo4j 写库（使用一个专用 modelId=999 做隔离，可事后 MATCH (n {modelId:999}) DETACH DELETE）
  - 不走 HTTP，直接在 Python 内部组装 app.state + FastAPI Request，复用 /api/extract 同一条代码路径

用法：
  cd pybackend
  # 可选：先清空上次联调的 999 模型图数据（自己在 Neo4j Browser 跑）
  # MATCH (n {modelId:999}) DETACH DELETE n; MATCH (:TimeAnchor {modelId:999}) DELETE n;
  python3 scripts/run_corpus_e2e.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

BASE_DIR = str(Path(__file__).resolve().parents[1])
CORPUS_PATH = os.path.join(BASE_DIR, "scripts", "corpus_bitemporal_demo.txt")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

from api.extraction import extract  # noqa: E402
from core.graph_writer import GraphWriter  # noqa: E402
from core.llm_client import LLMClient  # noqa: E402
from models.schemas import ExtractionRequest  # noqa: E402


# ============================================================================
# 专用 modelId：999 —— 用来隔离联调数据，不污染生产模型
# ============================================================================
DEMO_MODEL_ID = 999
DEMO_DOC_ID = "corpus_bitemporal_demo_v1"


def main() -> int:
    # 1) 读语料
    with open(CORPUS_PATH, "r", encoding="utf-8") as f:
        text = f.read().strip()
    print(f"[1/5] 已加载语料 {CORPUS_PATH}")
    print(f"      长度 = {len(text)} 字符，行数 = {text.count(chr(10))+1}")
    assert len(text) > 500, "语料太短，无法充分验证双时态+因果能力"

    # 2) 载入 config + 初始化依赖
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
    # ---- 语料级联调默认用 deepseek-chat：复杂结构化 JSON 长输出下比 v4-flash 更稳定
    #      （config.json 模型名不改；仅本脚本运行时临时覆盖，脚本外不受影响）
    overridden = False
    default_model = config["model"].get("model_name", "")
    prefer = os.environ.get("KG_E2E_MODEL", "deepseek-chat")
    if prefer and prefer != default_model:
        print(f"      💡  临时切换 LLM: {default_model} → {prefer}（仅本联调脚本，不改 config.json）")
        config["model"]["model_name"] = prefer
        overridden = True
    # 给复杂抽取更长超时（默认 120s 可能不够 2 次大 JSON 输出）
    config["model"].setdefault("timeout_sec", 180)
    config["model"].setdefault("max_retries", 1)

    print(f"[2/5] 初始化 LLMClient(model={config['model']['model_name']}, "
          f"timeout={config['model']['timeout_sec']}s) + GraphWriter")
    llm_client = LLMClient(config)
    graph_writer = GraphWriter(config)
    try:
        # 简单测 Neo4j 连通性（不执行写）
        with graph_writer.driver.session() as s:
            s.run("RETURN 1 AS ping")
        print("      Neo4j 连接 OK")
    except Exception as e:
        print(f"      ⚠️  Neo4j 连接失败：{e}（脚本将继续跑抽取+校验，只跳过写库）")
        graph_writer = None  # type: ignore

    # 3) 构造 ExtractionRequest
    req = ExtractionRequest(
        text=text,
        ontology={
            # 可选：给 LLM 一个轻量本体 hint，优先对齐这些类型（不强制，没命中会自由推断）
            "entityTypes": ["人物", "组织", "职位", "政策", "事件", "企业", "高校", "期刊", "学术机构"],
            "relationPredicates": ["担任", "任职于", "出任", "兼任", "晋升为", "分管",
                                  "服务于", "提供", "独立运营", "主编", "院长",
                                  "导致", "引发", "推高", "压缩", "缓解", "避免"],
        },
        modelId=DEMO_MODEL_ID,
        mode="llm_two_stage",
        docId=DEMO_DOC_ID,
    )

    # 4) 模仿 FastAPI：request.app.state.xxx 是 FastAPI 真实视图里的访问路径
    app_state = SimpleNamespace(
        llm_client=llm_client,
        graph_writer=graph_writer,
    )
    fake_app = SimpleNamespace(state=app_state)
    fake_request = SimpleNamespace(app=fake_app)

    print(f"[3/5] 开始走 /api/extract 内部函数；modelId={DEMO_MODEL_ID}, docId={DEMO_DOC_ID}")
    print("      （T1 第一遍 LLM + 质量墙 + T2 第二遍因果 + Neo4j 写库，预计 15~60 秒）")
    t0 = time.time()
    try:
        result = extract(req, fake_request)  # type: ignore
    except Exception as e:
        print("\n❌ extract() 抛异常：")
        traceback.print_exc()
        if graph_writer is not None:
            graph_writer.close()
        return 2
    dur = (time.time() - t0) * 1000

    # 5) 打印报告
    print("\n[4/5] 抽取汇总")
    print(f"      entities     = {len(result.entities)}")
    print(f"      timeAnchors  = {len(result.timeAnchors)}")
    print(f"      relations    = {len(result.relations)}")
    print(f"      causalEdges  = {len(result.causalEdges)}")
    print(f"      tokenConsumed= {result.tokenConsumed}")
    print(f"      duration(ms) = {result.duration}（FastAPI 内部计时）")
    print(f"      wall clock   = {int(dur)} ms")
    print(f"      writeCount   = {json.dumps(result.writeCount, ensure_ascii=False)}")
    print(f"      qualityStats = {json.dumps(result.qualityStats, ensure_ascii=False)}")

    print("\n[4.1] 实体清单")
    for i, e in enumerate(result.entities[:30], 1):
        # 预期字段：canonicalName / type / mention / span / kosCategory?
        cn = e.get("canonicalName") or e.get("name")
        typ = e.get("type", "")
        span = e.get("span", "")
        kos = e.get("kosCategory")
        tail = f"（KOS={kos}）" if kos else ""
        print(f"  {i:>2}. {cn} <{typ}>  span={span} {tail}")
    if len(result.entities) > 30:
        print(f"  ... 另 {len(result.entities)-30} 个实体已省略")

    print("\n[4.2] 时间锚点")
    for i, a in enumerate(result.timeAnchors, 1):
        print(f"  {i:>2}. {a.get('expr')!r}  type={a.get('type')}  "
              f"normISO={a.get('normISO')}  precision={a.get('precision')}  "
              f"span={a.get('span')}")

    print("\n[4.3] 关系清单（按 status 分组）")
    for status in ("CURRENT", "EXPIRED", "NEGATED"):
        sub = [r for r in result.relations if r.get("status") == status]
        if not sub:
            continue
        print(f"  —— status={status}（{len(sub)} 条）——")
        for i, r in enumerate(sub, 1):
            # api payload 用 head/relation/tail（兼容历史字段），语义等价于 subject/predicate/object
            s_ = r.get("head") or r.get("subject")
            p_ = r.get("relation") or r.get("predicate")
            o_ = r.get("tail") or r.get("object")
            vt_from = r.get("vt_from") or ""
            vt_to = r.get("vt_to") or ""
            vt = f"  VT=[{vt_from} → {vt_to}]" if vt_from or vt_to else "  VT=[无明确时间]"
            conf = r.get("confidence", 0)
            low = " [lowConf]" if r.get("lowConfidence") else ""
            neg = " [NEGATED=反事实]" if r.get("negated") else ""
            print(f"    {i}. ({s_})-[{p_}]->({o_})"
                  f"{vt}  conf={conf}{low}{neg}")

    print("\n[4.4] 因果边（按 FORWARD / PREVENT 展示）")
    if not result.causalEdges:
        print("  （无因果边产出；如果原文有因果但未抽到，检查 signalWord 和 T2 prompt）")
    for direction in ("FORWARD", "PREVENT"):
        sub = [c for c in result.causalEdges if c.get("direction") == direction]
        if not sub:
            continue
        print(f"  —— direction={direction}（{len(sub)} 条）——")
        for i, c in enumerate(sub, 1):
            sig = c.get("signalWord")
            vto = c.get("vt_order") or "UNKNOWN"
            conf = c.get("confidence", 0)
            low = " [lowConf]" if c.get("lowConfidence") else ""
            print(f"    {i}. {c.get('causeEvent')} → {c.get('effectEvent')}"
                  f"  signal={sig!r}  vt_order={vto}  conf={conf}{low}")

    print("\n[5/5] 质量问题清单（Semantica 式告警/剔除）")
    if not result.qualityReport:
        print("  ✅ 无任何质量告警（少见，通常至少几条 WARNING）")
    else:
        by_level: dict[str, list[dict]] = {}
        for it in result.qualityReport:
            by_level.setdefault(it.get("level", "?"), []).append(it)
        for lvl in ("DROPPED", "ERROR", "WARNING"):
            items = by_level.get(lvl, [])
            if not items:
                continue
            print(f"  —— [{lvl}] 共 {len(items)} 条 ——")
            for i, it in enumerate(items, 1):
                code = it.get("code")
                msg = it.get("message", "")
                if len(msg) > 160:
                    msg = msg[:160] + "…"
                print(f"    {i}. {code}: {msg}")

    # 简单人工校验：NEGATED / 因果边数量要有底线，否则给用户黄色提醒（非失败退出码）
    neg_cnt = sum(1 for r in result.relations if r.get("status") == "NEGATED")
    cau_cnt = len(result.causalEdges)
    print("\n" + "=" * 64)
    print(f"NEGATED 关系数 = {neg_cnt}（期望 ≥ 2：李建国辞独董 + 林毅夫 WB + 姚期智院长）")
    print(f"因果边数      = {cau_cnt}（期望 ≥ 3：医疗/经济/教育各至少 1 条 3 跳链）")
    if graph_writer is not None:
        print(
            f"写库成功       = entities={result.writeCount.get('entities')}  "
            f"relations={result.writeCount.get('relations')}  "
            f"causalEdges={result.writeCount.get('causalEdges')}  "
            f"missing_nodes_created={result.writeCount.get('missing_nodes_created')}"
        )
        print(
            "🧹 联调结束后，如需清理联调数据，可在 Neo4j Browser 执行：\n"
            "     MATCH (n {modelId:999}) DETACH DELETE n;\n"
            "     MATCH (a:TimeAnchor {modelId:999}) DELETE a;"
        )
    print("✅ 联调完成")

    if graph_writer is not None:
        graph_writer.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
