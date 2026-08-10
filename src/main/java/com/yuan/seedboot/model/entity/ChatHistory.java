package com.yuan.seedboot.model.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.util.Date;

@Data
@TableName("chat_history")
public class ChatHistory {

    @TableId(type = IdType.AUTO)
    private Long id;

    @TableField("message")
    private String message;

    @TableField("messageType")  // 明确指定数据库列名
    private String messageType;

    @TableField("sessionId")
    private String sessionId;

    @TableField("userId")
    private Long userId;

    @TableField("createTime")
    private Date createTime;

    @TableField("updateTime")
    private Date updateTime;

    @TableLogic
    @TableField("isDelete")
    private Integer isDelete;
}