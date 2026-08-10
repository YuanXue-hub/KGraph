package com.yuan.seedboot.model.request;

import com.yuan.seedboot.common.PageRequest;
import lombok.Data;
import lombok.EqualsAndHashCode;

import java.io.Serializable;

@EqualsAndHashCode(callSuper = true)
@Data
public class GraphProjectQueryRequest extends PageRequest implements Serializable {

    /**
     * 项目名称（模糊查询）
     */
    private String projectName;

    private static final long serialVersionUID = 1L;
}
