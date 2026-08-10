package com.yuan.seedboot.model.request;

import lombok.Data;

import java.io.Serializable;
import java.util.List;

/**
 * 基于深度学习的知识抽取请求
 */
@Data
public class ExtractionDlRequest implements Serializable {

    /**
     * 项目 id
     */
    private Long projectId;

    /**
     * 图谱模型 id
     */
    private Long modelId;

    /**
     * 语料 id（可选，与 inputText 二选一）
     */
    private Long corpusId;

    /**
     * 手动输入文本（与 corpusId 二选一）
     */
    private String inputText;

    /**
     * 深度学习抽取参数
     */
    private DlConfig dlConfig;

    @Data
    public static class DlConfig implements Serializable {
        /**
         * 实体识别类型（默认全部）
         */
        private List<String> entityTypes;

        /**
         * 置信度阈值（0.0-1.0，默认 0.5）
         */
        private Double confidenceThreshold = 0.5;

        /**
         * 最大实体数（默认 50）
         */
        private Integer maxEntities = 50;

        /**
         * 是否启用关系抽取：是 / 否
         */
        private String enableRelation = "是";

        /**
         * 关系置信度阈值（0.0-1.0，默认 0.3）
         */
        private Double relationThreshold = 0.3;

        /**
         * 上下文窗口大小（默认 5）
         */
        private Integer windowSize = 5;

        /**
         * 嵌入维度（默认 32）
         */
        private Integer embeddingDim = 32;

        /**
         * 模型架构：BiLSTM-CRF / CNN-Softmax / MLP-CRF
         */
        private String modelArchitecture = "BiLSTM-CRF";
    }

    private static final long serialVersionUID = 1L;
}
