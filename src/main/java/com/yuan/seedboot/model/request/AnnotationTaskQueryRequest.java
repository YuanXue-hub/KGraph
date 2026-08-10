package com.yuan.seedboot.model.request;

import com.yuan.seedboot.common.PageRequest;
import lombok.Data;
import lombok.EqualsAndHashCode;

import java.io.Serializable;

@EqualsAndHashCode(callSuper = true)
@Data
public class AnnotationTaskQueryRequest extends PageRequest implements Serializable {

    /**
     * 项目 id
     */
    private Long projectId;

    /**
     * 任务名称（模糊查询）
     */
    private String taskName;

    private static final long serialVersionUID = 1L;
}
