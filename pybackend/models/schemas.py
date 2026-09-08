from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ExtractionRequest(BaseModel):
    text: str
    ontology: Dict[str, Any]
    modelId: int
    mode: str = "zero_shot"
    docId: Optional[str] = None    # 可选：语料库原文 docId，用于证据追溯
    llmModelId: Optional[int] = None  # 抽取 LLM 模型（llm_model 表 id），空则用服务默认
    userId: Optional[int] = None   # 调用用户（Java 端注入，request_log 埋点归属）


class ExtractionResult(BaseModel):
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    relations: List[Dict[str, Any]] = Field(default_factory=list)
    timeAnchors: List[Dict[str, Any]] = Field(default_factory=list)  # 新增：LLM 抽的时间锚点
    causalEdges: List[Dict[str, Any]] = Field(default_factory=list)  # 新增：因果边 [:CAUSES]
    qualityReport: List[Dict[str, Any]] = Field(default_factory=list)  # 新增：Semantica 质量告警清单
    qualityStats: Dict[str, Any] = Field(default_factory=dict)       # 新增：质量计数统计
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


class SplitChunkItem(BaseModel):
    """单个分块：偏移量为原文闭区间"""
    index: int
    content: str
    startOffset: int
    endOffset: int
    charCount: int


class SplitRequest(BaseModel):
    text: str
    strategy: str = "fixed"
    chunkSize: Optional[int] = None
    overlap: Optional[int] = None
    separator: Optional[str] = None  # 仅 recursive 策略消费：自定义一级分隔符
    previewOnly: bool = False  # True 时仅返回前 10 块（totalChunks 仍为真实总数）


class SplitResult(BaseModel):
    strategy: str
    chunkSize: int
    overlap: int
    separator: Optional[str] = None
    totalChunks: int
    avgCharCount: int = 0
    duration: int = 0
    chunks: List[SplitChunkItem] = Field(default_factory=list)


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
    llmModelId: Optional[int] = None  # LLM 模型（llm_model 表 id），空则用默认
