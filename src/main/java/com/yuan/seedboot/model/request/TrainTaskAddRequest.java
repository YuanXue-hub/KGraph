package com.yuan.seedboot.model.request;

import lombok.Data;

import java.io.Serializable;

@Data
public class TrainTaskAddRequest implements Serializable {

    /**
     * 任务名称
     */
    private String taskName;

    /**
     * 项目 id
     */
    private Long projectId;

    /**
     * 标注任务 id
     */
    private Long annotationTaskId;

    /**
     * 数据集名称
     */
    private String dataset;

    /**
     * 模型架构
     */
    private String architecture;

    /**
     * 训练轮次
     */
    private Integer epochs;

    private static final long serialVersionUID = 1L;
}
