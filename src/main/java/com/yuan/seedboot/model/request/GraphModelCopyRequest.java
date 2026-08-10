package com.yuan.seedboot.model.request;

import lombok.Data;

import java.io.Serializable;

/**
 * 图谱模型复制请求
 */
@Data
public class GraphModelCopyRequest implements Serializable {

    /**
     * 源模型 id
     */
    private Long id;

    /**
     * 复制的模型名称
     */
    private String newModelName;

    /**
     * 复制的模型版本
     */
    private Integer newVersion;

    private static final long serialVersionUID = 1L;
}
