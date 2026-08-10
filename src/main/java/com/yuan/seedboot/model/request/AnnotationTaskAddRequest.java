package com.yuan.seedboot.model.request;

import lombok.Data;

import java.io.Serializable;

@Data
public class AnnotationTaskAddRequest implements Serializable {

    /**
     * 任务名称
     */
    private String taskName;

    /**
     * 项目 id
     */
    private Long projectId;

    /**
     * 语料 id
     */
    private Long corpusId;

    /**
     * 语料标题
     */
    private String corpusTitle;

    /**
     * 待标注文本
     */
    private String text;

    /**
     * 标注人
     */
    private String annotator;

    /**
     * 审核人
     */
    private String reviewer;

    private static final long serialVersionUID = 1L;
}
