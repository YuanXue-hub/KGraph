package com.yuan.seedboot.service.Impl;

import cn.hutool.core.util.ObjUtil;
import cn.hutool.core.util.StrUtil;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.UpdateWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.yuan.seedboot.exception.ErrorCode;
import com.yuan.seedboot.exception.ThrowUtils;
import com.yuan.seedboot.mapper.CorpusChunkMapper;
import com.yuan.seedboot.mapper.CorpusMapper;
import com.yuan.seedboot.model.entity.Corpus;
import com.yuan.seedboot.model.entity.User;
import com.yuan.seedboot.model.request.CorpusAddRequest;
import com.yuan.seedboot.model.request.CorpusQueryRequest;
import com.yuan.seedboot.model.request.CorpusUpdateRequest;
import com.yuan.seedboot.service.CorpusService;
import com.yuan.seedboot.service.MinerUService;
import com.yuan.seedboot.service.MinioService;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * @description 针对表【corpus(语料)】的数据库操作Service实现
 */
@Slf4j
@Service
public class CorpusServiceImpl extends ServiceImpl<CorpusMapper, Corpus>
        implements CorpusService {

    @Resource
    private MinioService minioService;

    @Resource
    private MinerUService minerUService;

    @Resource
    private CorpusChunkMapper corpusChunkMapper;

    private static final List<String> ALLOWED_FILE_TYPES = Arrays.asList("pdf", "doc", "docx");

    @Override
    public Corpus addCorpus(CorpusAddRequest request, User loginUser) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        ThrowUtils.throwIf(request.getProjectId() == null, ErrorCode.PARAMS_ERROR, "项目 id 为空");
        ThrowUtils.throwIf(StrUtil.isBlank(request.getContent()), ErrorCode.PARAMS_ERROR, "语料内容为空");
        Corpus corpus = new Corpus();
        BeanUtils.copyProperties(request, corpus);
        corpus.setSource("manual");
        corpus.setStatus(1); // 文本输入直接为已完成
        corpus.setCreateBy(loginUser.getId());
        boolean result = this.save(corpus);
        ThrowUtils.throwIf(!result, ErrorCode.OPERATION_ERROR, "新增语料失败");
        return corpus;
    }

    @Override
    public Corpus uploadCorpus(MultipartFile file, Long projectId, String title, User loginUser) {
        ThrowUtils.throwIf(file == null || file.isEmpty(), ErrorCode.PARAMS_ERROR, "文件为空");
        ThrowUtils.throwIf(projectId == null, ErrorCode.PARAMS_ERROR, "项目 id 为空");

        String originalFilename = file.getOriginalFilename();
        String fileType = extractFileType(originalFilename);
        ThrowUtils.throwIf(!ALLOWED_FILE_TYPES.contains(fileType), ErrorCode.PARAMS_ERROR,
                "仅支持 PDF、Word 文档");

        // 1. 上传文件到 MinIO
        String fileUrl = minioService.uploadFile(file, "corpus");

        // 2. 创建语料记录（状态为处理中）
        Corpus corpus = new Corpus();
        corpus.setProjectId(projectId);
        corpus.setTitle(StrUtil.isNotBlank(title) ? title : originalFilename);
        corpus.setContent("");
        corpus.setSource("file");
        corpus.setFilePath(fileUrl);
        corpus.setFileType(fileType);
        corpus.setStatus(0); // 处理中
        corpus.setCreateBy(loginUser.getId());
        boolean result = this.save(corpus);
        ThrowUtils.throwIf(!result, ErrorCode.OPERATION_ERROR, "新增语料失败");

        // 3. 异步调用 MinerU 解析
        minerUService.parseCorpusAsync(corpus.getId(), fileUrl, originalFilename);

        return corpus;
    }

    @Override
    public boolean reparseCorpus(Long id) {
        ThrowUtils.throwIf(id == null || id <= 0, ErrorCode.PARAMS_ERROR);
        Corpus corpus = this.getById(id);
        ThrowUtils.throwIf(ObjUtil.isNull(corpus), ErrorCode.NOT_FOUND_ERROR, "语料不存在");
        ThrowUtils.throwIf(!"file".equals(corpus.getSource()), ErrorCode.PARAMS_ERROR, "仅文档类型语料可重新解析");
        ThrowUtils.throwIf(StrUtil.isBlank(corpus.getFilePath()), ErrorCode.PARAMS_ERROR, "文件路径为空");

        // 重置状态为处理中（使用 UpdateWrapper 确保 errorMsg 被清除为 null）
        UpdateWrapper<Corpus> wrapper = new UpdateWrapper<>();
        wrapper.eq("id", id).set("status", 0).set("errorMsg", null);
        this.update(wrapper);
        // 重新解析将替换内容，原有分块失效，物理清空
        corpusChunkMapper.deleteByCorpusId(id);

        // 异步重新解析
        String fileName = corpus.getTitle() + "." + corpus.getFileType();
        minerUService.parseCorpusAsync(id, corpus.getFilePath(), fileName);

        return true;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public boolean updateCorpus(CorpusUpdateRequest request) {
        ThrowUtils.throwIf(request == null || request.getId() == null, ErrorCode.PARAMS_ERROR);
        Corpus corpus = new Corpus();
        BeanUtils.copyProperties(request, corpus);
        boolean result = this.updateById(corpus);
        ThrowUtils.throwIf(!result, ErrorCode.OPERATION_ERROR, "编辑语料失败");
        // 内容变更后原有分块偏移量失效，物理清空（前端依据行数据 chunkCount 提示重新分块）
        if (StrUtil.isNotBlank(request.getContent())) {
            corpusChunkMapper.deleteByCorpusId(request.getId());
        }
        return true;
    }

    @Override
    public Page<Corpus> listCorpus(CorpusQueryRequest request) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        long current = request.getPageNum();
        long pageSize = request.getPageSize();
        Long projectId = request.getProjectId();
        String title = request.getTitle();
        String sortField = request.getSortField();
        String sortOrder = request.getSortOrder();
        QueryWrapper<Corpus> queryWrapper = new QueryWrapper<>();
        queryWrapper.eq(ObjUtil.isNotNull(projectId), "projectId", projectId);
        queryWrapper.like(StrUtil.isNotBlank(title), "title", title);
        queryWrapper.orderBy(StrUtil.isNotBlank(sortField), "ascend".equals(sortOrder), sortField);
        Page<Corpus> page = this.page(new Page<>(current, pageSize), queryWrapper);
        fillChunkCount(page);
        return page;
    }

    /**
     * 填充每行语料的分块数（子查询聚合，分页规模下开销可忽略）
     */
    private void fillChunkCount(Page<Corpus> page) {
        List<Long> ids = page.getRecords().stream().map(Corpus::getId).collect(Collectors.toList());
        if (ids.isEmpty()) {
            return;
        }
        Map<Long, Long> countMap = corpusChunkMapper.countByCorpusIds(ids).stream()
                .collect(Collectors.toMap(
                        m -> ((Number) m.get("corpusId")).longValue(),
                        m -> ((Number) m.get("cnt")).longValue()));
        page.getRecords().forEach(c -> c.setChunkCount(countMap.getOrDefault(c.getId(), 0L)));
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public boolean deleteCorpus(Long id) {
        ThrowUtils.throwIf(id == null || id <= 0, ErrorCode.PARAMS_ERROR);
        Corpus corpus = this.getById(id);
        ThrowUtils.throwIf(ObjUtil.isNull(corpus), ErrorCode.NOT_FOUND_ERROR, "语料不存在");
        boolean result = this.removeById(id);
        // 级联物理清空分块，避免孤儿数据
        corpusChunkMapper.deleteByCorpusId(id);
        return result;
    }

    private String extractFileType(String filename) {
        if (StrUtil.isBlank(filename) || !filename.contains(".")) {
            return "";
        }
        return filename.substring(filename.lastIndexOf('.') + 1).toLowerCase();
    }
}
