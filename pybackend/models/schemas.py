from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ExtractionRequest(BaseModel):
    text: str
    ontology: Dict[str, Any]
    modelId: int
    mode: str = "zero_shot"


class ExtractionResult(BaseModel):
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    relations: List[Dict[str, Any]] = Field(default_factory=list)
    tokenConsumed: int = 0
    duration: int = 0
    writeCount: Dict[str, Any] = Field(default_factory=dict)


class KosExtractionRequest(BaseModel):
    text: str
    ontology: Optional[Dict[str, Any]] = None
    modelId: int
    kosConfig: Dict[str, Any] = Field(default_factory=dict)


class KosExtractionResult(BaseModel):
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    relations: List[Dict[str, Any]] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    tokenConsumed: int = 0
    duration: int = 0
    writeCount: Dict[str, Any] = Field(default_factory=dict)


class DlExtractionRequest(BaseModel):
    text: str
    ontology: Optional[Dict[str, Any]] = None
    modelId: int
    dlConfig: Dict[str, Any] = Field(default_factory=dict)


class DlExtractionResult(BaseModel):
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    relations: List[Dict[str, Any]] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    tokenConsumed: int = 0
    duration: int = 0
    writeCount: Dict[str, Any] = Field(default_factory=dict)


class TrainConfig(BaseModel):
    """训练配置"""
    architecture: str = "BiLSTM-CRF"
    learningRate: float = 0.001
    epochs: int = 20
    batchSize: int = 32
    embeddingDim: int = 64
    hiddenDim: int = 128
    dropout: float = 0.3
    optimizer: str = "Adam"
    validationSplit: float = 0.2
    gradClip: float = 5.0
    randomSeed: int = 42


class TrainRequest(BaseModel):
    """训练请求"""
    annotationData: Dict[str, Any] = Field(default_factory=dict)
    trainConfig: TrainConfig = Field(default_factory=TrainConfig)
    modelId: Optional[int] = None


class TrainHistoryItem(BaseModel):
    """训练历史单条"""
    epoch: int
    loss: float
    precision: float
    recall: float
    f1: float


class TrainResult(BaseModel):
    """训练结果"""
    history: List[Dict[str, Any]] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    duration: int = 0


class ChatAgentRequest(BaseModel):
    """智能问答 Agent 请求"""
    message: str
    modelId: int
    sessionId: Optional[str] = None
    userId: Optional[int] = None
