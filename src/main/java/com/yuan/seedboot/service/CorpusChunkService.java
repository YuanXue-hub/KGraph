package com.yuan.seedboot.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.yuan.seedboot.model.entity.CorpusChunk;
import com.yuan.seedboot.model.request.ChunkCorpusRequest;
import com.yuan.seedboot.model.vo.CorpusChunkStatsVO;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;

/**
 * 语料分块 Service
 */
public interface CorpusChunkService extends IService<CorpusChunk> {

    /**
     * 执行分块并落库（覆盖式重建：删旧块 + 插新块）
     */
    CorpusChunkStatsVO chunkCorpus(Long corpusId, ChunkCorpusRequest request, Long userId);

    /**
     * 分块预览（dry-run，不落库，返回统计 + 前 10 块）
     */
    CorpusChunkStatsVO previewChunks(Long corpusId, ChunkCorpusRequest request);

    /**
     * 分页查看块列表（按 chunkIndex 升序）
     */
    Page<CorpusChunk> pageChunks(Long corpusId, long pageNum, long pageSize);

    /**
     * 清空某语料全部分块（物理删）
     */
    boolean clearChunks(Long corpusId);
}
