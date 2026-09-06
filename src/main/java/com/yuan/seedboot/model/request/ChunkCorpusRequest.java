package com.yuan.seedboot.model.request;

import lombok.Data;

import java.io.Serializable;

/**
 * 分块执行/预览请求（参数快照与 Python /api/split 对齐）
 */
@Data
public class ChunkCorpusRequest implements Serializable {

    /**
     * 分块策略: fixed/sentence/recursive/structure
     */
    private String strategy;

    /**
     * 块大小（字符），空则取策略默认
     */
    private Integer chunkSize;

    /**
     * 重叠（字符），空则取策略默认
     */
    private Integer overlap;

    /**
     * 自定义一级分隔符（仅 recursive 策略，如 \n\n、###）
     */
    private String separator;

    private static final long serialVersionUID = 1L;
}
