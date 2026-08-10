"""深度学习模型训练 API 端点。"""
from fastapi import APIRouter, HTTPException, Request

from core.trainer import train as run_train
from models.schemas import TrainRequest, TrainResult

router = APIRouter()


@router.post("/api/train", response_model=TrainResult)
def train_endpoint(req: TrainRequest, request: Request) -> TrainResult:
    """深度学习模型训练：基于标注数据模拟训练过程，返回训练曲线和指标。"""
    try:
        result = run_train(req.annotationData, req.trainConfig)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"训练失败: {e}")

    return TrainResult(
        history=result['history'],
        metrics=result['metrics'],
        duration=result['duration'],
    )
