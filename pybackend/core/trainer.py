"""深度学习模型训练器（模拟训练，基于标注数据量生成合理曲线）。"""
import math
import random
import time
from typing import Any, Dict, List


def train(annotation_data: Dict[str, Any], train_config: Any) -> Dict[str, Any]:
    """
    模拟深度学习模型训练过程。

    基于标注数据量（实体数、关系数）和训练配置（epochs、architecture），
    生成合理的 Loss 下降曲线和 P/R/F1 上升曲线。

    Args:
        annotation_data: 标注数据 {entities: [...], relations: [...]}
        train_config: 训练配置

    Returns:
        {history: [{epoch, loss, precision, recall, f1}], metrics: {loss, precision, recall, f1}, duration: ms}
    """
    start = time.time()

    entities = annotation_data.get("entities", []) if isinstance(annotation_data, dict) else []
    relations = annotation_data.get("relations", []) if isinstance(annotation_data, dict) else []
    entity_count = len(entities) if isinstance(entities, list) else 0
    relation_count = len(relations) if isinstance(relations, list) else 0

    # 从配置获取参数
    epochs = getattr(train_config, 'epochs', 20) or 20
    architecture = getattr(train_config, 'architecture', 'BiLSTM-CRF') or 'BiLSTM-CRF'

    # 根据架构调整收敛速度（BERT 收敛更快但初始 loss 更低）
    arch_factor = {
        'BERT-CRF': 0.22,
        'SPAN-BERT': 0.20,
        'BERT-RE': 0.18,
        'BiLSTM-CRF': 0.16,
    }.get(architecture, 0.16)

    # 根据标注数据量调整最终指标上限（数据越多指标越好）
    data_bonus = min(0.05, (entity_count + relation_count) * 0.005)

    history: List[Dict[str, Any]] = []
    random.seed(42)

    for epoch in range(1, epochs + 1):
        # Loss: 指数衰减 + 随机噪声
        base_loss = max(0.03, 2.5 * math.exp(-epoch * arch_factor))
        noise = (random.random() - 0.5) * 0.06
        loss = round(base_loss + noise, 4)

        # Precision/Recall: S 型上升
        precision = min(0.99, 0.35 + 0.58 * (1 - math.exp(-epoch * (arch_factor + 0.04))) + data_bonus + (random.random() - 0.5) * 0.015)
        recall = min(0.99, 0.30 + 0.63 * (1 - math.exp(-epoch * (arch_factor + 0.03))) + data_bonus + (random.random() - 0.5) * 0.015)
        f1 = round(2 * precision * recall / (precision + recall), 4)
        precision = round(precision, 4)
        recall = round(recall, 4)

        history.append({
            'epoch': epoch,
            'loss': loss,
            'precision': precision,
            'recall': recall,
            'f1': f1,
        })

    final = history[-1] if history else {'loss': 0, 'precision': 0, 'recall': 0, 'f1': 0}
    metrics = {
        'loss': final['loss'],
        'precision': final['precision'],
        'recall': final['recall'],
        'f1': final['f1'],
    }

    duration = int((time.time() - start) * 1000)

    return {
        'history': history,
        'metrics': metrics,
        'duration': duration,
    }
