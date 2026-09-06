package com.yuan.seedboot.service.Impl;

import cn.hutool.core.util.StrUtil;
import cn.hutool.json.JSONArray;
import cn.hutool.json.JSONObject;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.yuan.seedboot.config.PythonServiceClient;
import com.yuan.seedboot.exception.ErrorCode;
import com.yuan.seedboot.exception.ThrowUtils;
import com.yuan.seedboot.mapper.CorpusChunkMapper;
import com.yuan.seedboot.model.entity.Corpus;
import com.yuan.seedboot.model.entity.CorpusChunk;
import com.yuan.seedboot.model.request.ChunkCorpusRequest;
import com.yuan.seedboot.model.vo.CorpusChunkStatsVO;
import com.yuan.seedboot.service.CorpusChunkService;
import com.yuan.seedboot.service.CorpusService;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Date;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * 语料分块 Service 实现：Python 无状态计算 + Java 事务落库
 */
@Slf4j
@Service
public class CorpusChunkServiceImpl extends ServiceImpl<CorpusChunkMapper, CorpusChunk>
        implements CorpusChunkService {

    private static final Set<String> ALLOWED_STRATEGIES =
            Set.of("fixed", "sentence", "recursive", "structure");

    @Resource
    private CorpusService corpusService;

    @Resource
    private PythonServiceClient pythonServiceClient;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public CorpusChunkStatsVO chunkCorpus(Long corpusId, ChunkCorpusRequest request, Long userId) {
        Corpus corpus = validateAndGetCorpus(corpusId, request);

        JSONObject resp = pythonServiceClient.splitText(corpus.getContent(),
                request.getStrategy(), request.getChunkSize(), request.getOverlap(),
                request.getSeparator(), false);

        List<CorpusChunk> chunks = parseChunks(resp, corpus, userId, request);

        // 覆盖式重建：物理删旧块 + 批量插新块（UNIQUE KEY 兜底）
        this.baseMapper.deleteByCorpusId(corpusId);
        if (!chunks.isEmpty()) {
            this.saveBatch(chunks, 500);
        }
        log.info("语料分块完成, corpusId={}, strategy={}, totalChunks={}",
                corpusId, request.getStrategy(), chunks.size());
        return buildStats(resp, request, null);
    }

    @Override
    public CorpusChunkStatsVO previewChunks(Long corpusId, ChunkCorpusRequest request) {
        Corpus corpus = validateAndGetCorpus(corpusId, request);

        JSONObject resp = pythonServiceClient.splitText(corpus.getContent(),
                request.getStrategy(), request.getChunkSize(), request.getOverlap(),
                request.getSeparator(), true);

        List<CorpusChunk> preview = parseChunks(resp, corpus, null, request);
        return buildStats(resp, request, preview);
    }

    @Override
    public Page<CorpusChunk> pageChunks(Long corpusId, long pageNum, long pageSize) {
        ThrowUtils.throwIf(corpusId == null || corpusId <= 0, ErrorCode.PARAMS_ERROR);
        QueryWrapper<CorpusChunk> wrapper = new QueryWrapper<>();
        wrapper.eq("corpusId", corpusId).orderByAsc("chunkIndex");
        return this.page(new Page<>(pageNum, pageSize), wrapper);
    }

    @Override
    public boolean clearChunks(Long corpusId) {
        ThrowUtils.throwIf(corpusId == null || corpusId <= 0, ErrorCode.PARAMS_ERROR);
        Corpus corpus = corpusService.getById(corpusId);
        ThrowUtils.throwIf(corpus == null, ErrorCode.NOT_FOUND_ERROR, "语料不存在");
        this.baseMapper.deleteByCorpusId(corpusId);
        return true;
    }

    private Corpus validateAndGetCorpus(Long corpusId, ChunkCorpusRequest request) {
        ThrowUtils.throwIf(request == null || StrUtil.isBlank(request.getStrategy()),
                ErrorCode.PARAMS_ERROR, "分块策略为空");
        ThrowUtils.throwIf(!ALLOWED_STRATEGIES.contains(request.getStrategy()),
                ErrorCode.PARAMS_ERROR, "未知分块策略: " + request.getStrategy());
        ThrowUtils.throwIf(corpusId == null || corpusId <= 0, ErrorCode.PARAMS_ERROR);

        Corpus corpus = corpusService.getById(corpusId);
        ThrowUtils.throwIf(corpus == null, ErrorCode.NOT_FOUND_ERROR, "语料不存在");
        ThrowUtils.throwIf(corpus.getStatus() == null || corpus.getStatus() != 1,
                ErrorCode.PARAMS_ERROR, "语料尚未解析完成，暂不可分块");
        ThrowUtils.throwIf(StrUtil.isBlank(corpus.getContent()), ErrorCode.PARAMS_ERROR, "语料内容为空");
        return corpus;
    }

    private List<CorpusChunk> parseChunks(JSONObject resp, Corpus corpus, Long userId,
                                          ChunkCorpusRequest request) {
        JSONArray arr = resp.getJSONArray("chunks");
        ThrowUtils.throwIf(arr == null || arr.isEmpty(), ErrorCode.PARAMS_ERROR, "分块结果为空");
        Date now = new Date();
        return arr.stream().map(o -> {
            JSONObject c = (JSONObject) o;
            CorpusChunk chunk = new CorpusChunk();
            chunk.setCorpusId(corpus.getId());
            chunk.setProjectId(corpus.getProjectId());
            chunk.setChunkIndex(c.getInt("index"));
            chunk.setContent(c.getStr("content"));
            chunk.setStartOffset(c.getInt("startOffset"));
            chunk.setEndOffset(c.getInt("endOffset"));
            chunk.setCharCount(c.getInt("charCount"));
            chunk.setStrategy(resp.getStr("strategy"));
            chunk.setChunkSize(resp.getInt("chunkSize"));
            chunk.setOverlap(resp.getInt("overlap"));
            // 快照存用户字面量输入（如 \n\n），重新分块时可直接回填表单
            chunk.setCustomSeparator(StrUtil.blankToDefault(request.getSeparator(), null));
            chunk.setCreateBy(userId);
            chunk.setCreateTime(now);
            return chunk;
        }).collect(Collectors.toList());
    }

    private CorpusChunkStatsVO buildStats(JSONObject resp, ChunkCorpusRequest request,
                                          List<CorpusChunk> previewChunks) {
        CorpusChunkStatsVO vo = new CorpusChunkStatsVO();
        vo.setStrategy(resp.getStr("strategy"));
        vo.setChunkSize(resp.getInt("chunkSize"));
        vo.setOverlap(resp.getInt("overlap"));
        // 回显用户字面量输入，便于表单回填
        vo.setSeparator(StrUtil.blankToDefault(request.getSeparator(), null));
        vo.setTotalChunks(resp.getInt("totalChunks"));
        vo.setAvgCharCount(resp.getInt("avgCharCount"));
        vo.setDuration(resp.getInt("duration"));
        vo.setPreviewChunks(previewChunks);
        return vo;
    }
}
