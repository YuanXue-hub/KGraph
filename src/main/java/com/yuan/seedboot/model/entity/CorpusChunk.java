package com.yuan.seedboot.model.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.io.Serializable;
import java.util.Date;

/**
 * 语料分块实体（对应 corpus_chunk 表）
 */
@TableName(value = "corpus_chunk")
@Data
public class CorpusChunk implements Serializable {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    @TableField("corpusId")
    private Long corpusId;

    @TableField("projectId")
    private Long projectId;

    /** 块序号，从 0 开始 */
    @TableField("chunkIndex")
    private Integer chunkIndex;

    @TableField("content")
    private String content;

    /** 块起始偏移（闭区间，含） */
    @TableField("startOffset")
    private Integer startOffset;

    /** 块结束偏移（闭区间，含） */
    @TableField("endOffset")
    private Integer endOffset;

    @TableField("charCount")
    private Integer charCount;

    /** 分块策略: fixed/sentence/recursive/structure */
    @TableField("strategy")
    private String strategy;

    /** 生成时的块大小参数（快照） */
    @TableField("chunkSize")
    private Integer chunkSize;

    /** 生成时的重叠参数（快照） */
    @TableField("overlap")
    private Integer overlap;

    /** 生成时的自定义分隔符（快照，仅 recursive 策略） */
    @TableField("customSeparator")
    private String customSeparator;

    @TableField("createBy")
    private Long createBy;

    @TableField("createTime")
    private Date createTime;

    @TableLogic
    @TableField("isDeleted")
    private Integer isDeleted;

    private static final long serialVersionUID = 1L;
}
