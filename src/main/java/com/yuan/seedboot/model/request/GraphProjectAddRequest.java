package com.yuan.seedboot.model.request;

import lombok.Data;

import java.io.Serializable;

@Data
public class GraphProjectAddRequest implements Serializable {

    /**
     * 项目名称
     */
    private String projectName;

    /**
     * 项目描述
     */
    private String projectDescription;

    private static final long serialVersionUID = 1L;
}
