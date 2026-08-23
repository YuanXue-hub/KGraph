"""
Browser E2E: 4领域LLM抽取批量测试脚本
直接调用 Python backend /api/extract endpoint（对应Java端的LLM抽取）
写入的 modelId 固定为浏览器创建的测试模型
"""
import json
import time
import requests
import sys
from pathlib import Path

# ====== 配置 ======
PYBACKEND_URL = "http://localhost:8001"
PROJECT_ID = 2091150698975645698  # Browser-E2E多领域测试
MODEL_ID = 2091152701076328449     # 多领域LLM抽取测试模型

# 4领域语料（与浏览器创建时一致）
CORPORA = [
    {
        "domain": "领域2-科技产业",
        "short": "tech",
        "text": (
            "2025年3月15日，字节跳动宣布成立人工智能实验室（ByteDance AI Lab），由原谷歌DeepMind研究员李明博士担任实验室主任，"
            "总部设在北京海淀区中关村科技园。该实验室首期投入50亿元人民币，重点研究大语言模型、多模态生成与具身智能三大方向。"
            "同年5月20日，字节跳动收购了专注于AI芯片设计的初创公司弘芯微电子，交易金额约为12亿美元，弘芯微电子创始人王强及核心团队全部加入字节跳动，"
            "担任AI基础设施部门首席架构师职务。2025年9月1日，字节跳动正式发布旗下新一代大语言模型Doubao-3，参数规模达到4000亿，"
            "在MMLU、HumanEval等权威基准测试中超越同期Meta的Llama 3模型，排名全球第二。Doubao-3由字节跳动副总裁兼技术委员会主席张伟亲自挂帅带队研发，"
            "历时18个月完成训练。值得注意的是，此前市场传言腾讯公司曾于2024年底洽谈收购弘芯微电子，但最终因估值分歧未能达成协议。"
        ),
    },
    {
        "domain": "领域3-金融财经",
        "short": "finance",
        "text": (
            "中国人民银行于2026年1月15日宣布下调金融机构存款准备金率0.5个百分点，预计释放长期流动性约1.2万亿元人民币。"
            "此次降准旨在改善银行体系流动性结构，降低社会综合融资成本，支持实体经济发展。受降准消息影响，1月16日A股上证指数收盘上涨1.8%，"
            "深证成指上涨2.3%，沪深300指数上涨2.1%；其中银行板块平均涨幅3.2%，地产板块涨幅4.5%，万科A、保利发展等龙头房企涨停。"
            "与此同时，10年期国债收益率下行8个基点至2.48%，市场对后续宽松政策预期升温。中金公司首席经济学家彭文生在研究报告中指出，"
            "若后续经济复苏力度不及预期，央行可能于第二季度再次降准0.25个百分点，并同步调降MLF利率。但是，中信证券宏观分析师明明团队提示，"
            "美国联邦储备委员会若维持高利率时间过长，将制约中国央行进一步宽松的空间，人民币汇率贬值压力可能在第二季度阶段性显现。"
        ),
    },
    {
        "domain": "领域4-学术科研",
        "short": "academic",
        "text": (
            "清华大学交叉信息研究院姚期智院士团队于2026年2月在《自然·物理学》（Nature Physics）期刊在线发表题为《基于127量子比特超导处理器的拓扑量子纠错实验》的研究论文。"
            "论文第一作者为清华大学物理系2023级博士研究生陈小雨，通讯作者为姚期智院士及段路明教授。"
            "该研究依托国家重点研发计划量子信息与量子科技创新专项（项目编号：2025YFA0309800），在合肥微尺度物质科学国家研究中心完成核心实验。"
            "实验结果表明，研究团队成功实现了表面码距离为7的逻辑比特纠错，逻辑错误率较未纠错时降低了两个数量级，"
            "该成果被审稿人评价为迈向容错量子计算的里程碑。此前，2025年6月，中国科学技术大学潘建伟团队曾在《科学》（Science）杂志发表类似架构的72量子比特纠错实验，"
            "但两者在比特连通性和保真度指标上存在显著差异。"
        ),
    },
]


def _empty_ontology() -> dict:
    """新创建的测试模型本体为空，传空的 entities/relations 即可"""
    return {"entities": [], "relations": []}


def run_extract(domain: str, text: str) -> dict:
    # pybackend /api/extract 接口签名 = Pydantic ExtractionRequest
    # fields: text, ontology, modelId, mode, docId
    payload = {
        "text": text,
        "ontology": _empty_ontology(),
        "modelId": int(MODEL_ID),  # 确保是int（即使超过JS安全范围，Python本身没问题）
        "mode": "few_shot",
        "docId": None,
    }
    t0 = time.time()
    r = requests.post(f"{PYBACKEND_URL}/api/extract", json=payload, timeout=600)
    if r.status_code != 200:
        print(f"  ~~ 响应原文前500字符: {r.text[:500]}", flush=True)
    r.raise_for_status()
    dt = time.time() - t0
    data = r.json()
    data["_wall_seconds"] = round(dt, 2)
    return data


def summarize(result: dict) -> dict:
    entities = result.get("entities") or []
    anchors = result.get("timeAnchors") or []
    relations = result.get("relations") or []
    causals = result.get("causalEdges") or []
    report = result.get("qualityReport") or {}
    issues = report.get("issues") or []
    return {
        "wall_seconds": result.get("_wall_seconds", -1),
        "entities": len(entities),
        "time_anchors": len(anchors),
        "relations": len(relations),
        "negated_relations": sum(1 for r in relations if (r.get("status") or "").upper() == "NEGATED"),
        "causal_edges": len(causals),
        "causal_prevent": sum(1 for c in causals if (c.get("direction") or "").upper() == "PREVENT"),
        "token_consumed": result.get("tokenConsumed", 0),
        "issues_total": len(issues),
        "issues_by_level": report.get("byLevel", {}),
        "write_ok": result.get("writeResult", {}).get("ok", False),
    }


def main():
    results = []
    for c in CORPORA:
        print(f"\n=== [{c['domain']}] 开始抽取 ({len(c['text'])} 字符) ===", flush=True)
        try:
            raw = run_extract(c["domain"], c["text"])
            summary = summarize(raw)
            print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
            results.append({
                "domain": c["domain"],
                "short": c["short"],
                "summary": summary,
            })
            # 保存完整结果文件（详细）
            out = Path(__file__).parent / f"llm4dom_{c['short']}_full.json"
            out.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  -> 完整结果已保存: {out}", flush=True)
        except Exception as e:
            print(f"  !! ERROR: {type(e).__name__}: {e}", flush=True)
            results.append({"domain": c["domain"], "short": c["short"], "error": f"{type(e).__name__}: {e}"})

    # 汇总对比
    print("\n" + "=" * 70, flush=True)
    print(" 4 领域 LLM 抽取效果对比汇总", flush=True)
    print("=" * 70, flush=True)
    header = f"{'领域':<16}{'实体':>6}{'时态锚':>7}{'关系':>6}{'NEG':>5}{'因果':>6}{'PREV':>5}{'耗时(s)':>9}{'token':>8}{'问题数':>7}{'写入':>5}"
    print(header)
    print("-" * len(header))
    for r in results:
        if "error" in r:
            print(f"{r['domain']:<16} ERROR: {r['error'][:50]}")
            continue
        s = r["summary"]
        neg = s["negated_relations"]
        prev = s["causal_prevent"]
        ok = "✓" if s["write_ok"] else "✗"
        print(
            f"{r['domain']:<16}{s['entities']:>6}{s['time_anchors']:>7}{s['relations']:>6}"
            f"{neg:>5}{s['causal_edges']:>6}{prev:>5}{s['wall_seconds']:>9.1f}{s['token_consumed']:>8}"
            f"{s['issues_total']:>7}{ok:>5}"
        )
    # 再保存完整汇总
    summary_file = Path(__file__).parent / "llm4dom_summary.json"
    summary_file.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n汇总文件已保存: {summary_file}")


if __name__ == "__main__":
    main()
