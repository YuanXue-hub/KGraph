package com.yuan.seedboot.model.request;

import lombok.Data;

import java.io.Serializable;

@Data
public class GraphModelUpdateRequest implements Serializable {

    /**
     * 模型 id
     */
    private Long id;

    /**
     * 模型名称
     */
    private String modelName;

    /**
     * 模型描述
     */
    private String modelDescription;

    private static final long serialVersionUID = 1L;
}
