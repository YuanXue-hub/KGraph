package com.yuan.seedboot.model.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.util.Date;

/**
 * LLM 抽取质量评估历史（对应表 evaluation_record）
 */
@TableName(value = "evaluation_record")
@Data
public class EvaluationRecord {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    @TableField("taskId")
    private Long taskId;

    @TableField("sampleSize")
    private Integer sampleSize;

    @TableField("overall")
    private Double overall;

    @TableField("result")
    private String result;

    @TableField("tokenConsumed")
    private Integer tokenConsumed;

    @TableField("duration")
    private Long duration;

    @TableLogic
    @TableField("isDeleted")
    private Integer isDeleted;

    @TableField("createBy")
    private Long createBy;

    @TableField("createTime")
    private Date createTime;
}
