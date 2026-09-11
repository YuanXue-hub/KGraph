"""KGraph vs Semantica 对比实验服务（端口 8002，WarSee 独立进程）。

职责边界：
  · POST /api/extract —— Semantica 两阶段抽取 + KGraph schema 适配（不写 Neo4j）
  · GET  /api/corpora  —— 只读 MySQL corpus 表（语料选择）
  · GET  /api/models   —— 只读 llm_model 表（抽取模型选择，与 KGraph 共用同一模型保证公平）
  · GET  /             —— 静态对比页（static/index.html）

主服务 8001 不做任何改动即可被本页调用（抽取 dryRun / 评估 API）。
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

import pymysql
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 复用主服务的 config.json（模型 / MySQL 连接），只读不写
CONFIG = json.load(open(os.path.join(BASE_DIR, "..", "config.json"), encoding="utf-8"))

MYSQL_CFG = CONFIG["memory"]["mysql"]

app = FastAPI(title="KGraph vs Semantica 对比实验服务")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _mysql():
    return pymysql.connect(
        host=MYSQL_CFG["host"], port=int(MYSQL_CFG["port"]),
        user=MYSQL_CFG["user"], password=MYSQL_CFG["password"],
        database=MYSQL_CFG["database"], charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


# ============================================================================
# 数据接口
# ============================================================================
@app.get("/api/corpora")
def list_corpora() -> List[Dict[str, Any]]:
    """语料列表（id / 标题 / 字数 / 项目），只读。"""
    try:
        with _mysql() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, title, projectId, char_length(content) AS charCount, "
                "createTime FROM corpus WHERE isDeleted=0 AND status=1 "
                "ORDER BY id DESC LIMIT 100"
            )
            rows = cur.fetchall()
        for r in rows:
            r["id"] = str(r["id"])   # 雪花 ID 超过 JS Number 安全范围，必须以字符串返回
            r["createTime"] = str(r.pop("createTime", "") or "")
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"语料列表读取失败: {e}")


@app.get("/api/corpora/{corpus_id}")
def get_corpus(corpus_id: int) -> Dict[str, Any]:
    try:
        with _mysql() as conn, conn.cursor() as cur:
            cur.execute("SELECT id, title, content FROM corpus WHERE id=%s", (corpus_id,))
            row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="语料不存在")
        row["id"] = str(row["id"])   # 同上：雪花 ID 以字符串返回，避免 JS 精度丢失
        return row
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"语料读取失败: {e}")


@app.get("/api/models")
def list_models() -> List[Dict[str, Any]]:
    """可用抽取模型（与 KGraph 共用 llm_model 表，保证对比实验同模型）。"""
    try:
        with _mysql() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, model_name, display_name, provider FROM llm_model "
                "WHERE enabled=1 ORDER BY id"
            )
            return cur.fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"模型列表读取失败: {e}")


# ============================================================================
# 抽取接口
# ============================================================================
class SemanticaExtractRequest(BaseModel):
    text: str
    llmModelId: Optional[int] = None   # llm_model 表 id；空则用 config.json 默认模型
    entityTypes: List[str] = Field(default_factory=list)
    fairness: bool = True                # 公平校验墙（对齐 KGraph W1-W5 的等价后处理）


@app.post("/api/extract")
def extract(req: SemanticaExtractRequest) -> Dict[str, Any]:
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="待抽取文本为空")

    # 模型解析：llmModelId 优先（与 KGraph 抽取用同一模型，控制变量），否则回退默认配置
    model_name = CONFIG["model"]["model_name"]
    api_key = CONFIG["model"]["api_key"]
    base_url = CONFIG["model"]["base_url"]
    if req.llmModelId:
        try:
            with _mysql() as conn, conn.cursor() as cur:
                cur.execute(
                    "SELECT model_name, api_key, base_url FROM llm_model "
                    "WHERE id=%s AND enabled=1", (int(req.llmModelId),),
                )
                row = cur.fetchone()
            if row:
                model_name, api_key, base_url = (
                    row["model_name"], row["api_key"], row["base_url"])
        except Exception:
            pass  # 回退默认配置

    from extractor import run_semantica_extraction

    try:
        result = run_semantica_extraction(
            text, model_name=model_name, api_key=api_key, base_url=base_url,
            entity_types=req.entityTypes or None,
        )
        if req.fairness:
            from fairness import apply_fairness_wall
            result = apply_fairness_wall(result, text)
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Semantica 抽取失败: {e}")


@app.get("/")
def index():
    return FileResponse(os.path.join(BASE_DIR, "static", "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
