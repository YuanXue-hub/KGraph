package com.yuan.seedboot.model.request;

import lombok.Data;

import java.io.Serializable;

@Data
public class AnnotationTaskUpdateRequest implements Serializable {

    /**
     * 任务 id
     */
    private Long id;

    /**
     * 任务名称
     */
    private String taskName;

    /**
     * 标注人
     */
    private String annotator;

    /**
     * 审核人
     */
    private String reviewer;

    /**
     * 实体标注（JSON 字符串，保存标注进度）
     */
    private String entities;

    /**
     * 关系标注（JSON 字符串，保存标注进度）
     */
    private String relations;

    /**
     * 总句数
     */
    private Integer totalSentences;

    /**
     * 已标注句数
     */
    private Integer annotatedSentences;

    private static final long serialVersionUID = 1L;
}
