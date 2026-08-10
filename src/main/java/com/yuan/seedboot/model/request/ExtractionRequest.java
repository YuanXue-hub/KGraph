package com.yuan.seedboot.model.request;

import lombok.Data;

import java.io.Serializable;
import java.util.List;

@Data
public class ExtractionRequest implements Serializable {

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
     * 抽取模式: zero_shot / few_shot / open
     */
    private String mode;

    /**
     * 自定义实体类型（可选，提供时覆盖模型本体）
     */
    private List<String> customEntityTypes;

    /**
     * 自定义关系类型（可选，提供时覆盖模型本体）
     */
    private List<String> customRelationTypes;

    private static final long serialVersionUID = 1L;
}
