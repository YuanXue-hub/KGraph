package com.yuan.seedboot.model.vo;

import com.yuan.seedboot.model.entity.CorpusChunk;
import lombok.Data;

import java.io.Serializable;
import java.util.List;

/**
 * 分块执行/预览结果统计 VO
 */
@Data
public class CorpusChunkStatsVO implements Serializable {

    /**
     * 生效策略
     */
    private String strategy;

    /**
     * 生效块大小（钳制后）
     */
    private Integer chunkSize;

    /**
     * 生效重叠（钳制后）
     */
    private Integer overlap;

    /**
     * 生效自定义分隔符（仅 recursive）
     */
    private String separator;

    /**
     * 总块数
     */
    private Integer totalChunks;

    /**
     * 平均块长（字符）
     */
    private Integer avgCharCount;

    /**
     * 计算耗时（毫秒）
     */
    private Integer duration;

    /**
     * 预览块（仅 preview 接口返回，前 10 块）
     */
    private List<CorpusChunk> previewChunks;

    private static final long serialVersionUID = 1L;
}
