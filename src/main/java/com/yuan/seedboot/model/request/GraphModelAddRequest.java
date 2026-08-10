package com.yuan.seedboot.model.request;

import lombok.Data;

import java.io.Serializable;

@Data
public class GraphModelAddRequest implements Serializable {

    /**
     * 项目 id
     */
    private Long projectId;

    /**
     * 模型名称
     */
    private String modelName;

    /**
     * 模型描述
     */
    private String modelDescription;

    /**
     * 模型版本
     */
    private Integer version;

    private static final long serialVersionUID = 1L;
}
