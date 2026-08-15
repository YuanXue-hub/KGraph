package com.yuan.seedboot.model.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.util.Date;

@TableName(value = "corpus")
@Data
public class Corpus {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    @TableField("projectId")
    private Long projectId;

    @TableField("title")
    private String title;

    @TableField("content")
    private String content;

    @TableField("source")
    private String source;

    @TableField("filePath")
    private String filePath;

    /** 文件类型: pdf/docx（仅文档上传时有值） */
    @TableField("fileType")
    private String fileType;

    /** MinerU 任务 ID（文档解析用） */
    @TableField("mineruTaskId")
    private String mineruTaskId;

    /** 解析失败原因 */
    @TableField("errorMsg")
    private String errorMsg;

    /** 状态: 0-处理中 1-已完成 2-失败 */
    @TableField("status")
    private Integer status;

    @TableField("createBy")
    private Long createBy;

    @TableField("createTime")
    private Date createTime;

    @TableField("updateTime")
    private Date updateTime;

    @TableLogic
    @TableField("isDeleted")
    private Integer isDeleted;
}
