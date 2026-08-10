package com.yuan.seedboot.model.request;

import com.yuan.seedboot.common.PageRequest;
import lombok.Data;
import lombok.EqualsAndHashCode;

import java.io.Serializable;

@EqualsAndHashCode(callSuper = true)
@Data
public class TrainTaskQueryRequest extends PageRequest implements Serializable {

    /**
     * 项目 id
     */
    private Long projectId;

    /**
     * 任务状态: pending/training/done/failed
     */
    private String status;

    /**
     * 模型架构
     */
    private String architecture;

    private static final long serialVersionUID = 1L;
}
