package com.yuan.seedboot.service.Impl;

import cn.hutool.core.util.ObjUtil;
import cn.hutool.core.util.StrUtil;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.yuan.seedboot.exception.ErrorCode;
import com.yuan.seedboot.exception.ThrowUtils;
import com.yuan.seedboot.mapper.CorpusMapper;
import com.yuan.seedboot.model.entity.Corpus;
import com.yuan.seedboot.model.entity.User;
import com.yuan.seedboot.model.request.CorpusAddRequest;
import com.yuan.seedboot.model.request.CorpusQueryRequest;
import com.yuan.seedboot.model.request.CorpusUpdateRequest;
import com.yuan.seedboot.service.CorpusService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Service;

/**
 * @description 针对表【corpus(语料)】的数据库操作Service实现
 */
@Slf4j
@Service
public class CorpusServiceImpl extends ServiceImpl<CorpusMapper, Corpus>
        implements CorpusService {

    @Override
    public Corpus addCorpus(CorpusAddRequest request, User loginUser) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        ThrowUtils.throwIf(request.getProjectId() == null, ErrorCode.PARAMS_ERROR, "项目 id 为空");
        ThrowUtils.throwIf(StrUtil.isBlank(request.getContent()), ErrorCode.PARAMS_ERROR, "语料内容为空");
        Corpus corpus = new Corpus();
        BeanUtils.copyProperties(request, corpus);
        corpus.setSource(StrUtil.blankToDefault(request.getSource(), "manual"));
        corpus.setStatus(0);
        corpus.setCreateBy(loginUser.getId());
        boolean result = this.save(corpus);
        ThrowUtils.throwIf(!result, ErrorCode.OPERATION_ERROR, "新增语料失败");
        return corpus;
    }

    @Override
    public boolean updateCorpus(CorpusUpdateRequest request) {
        ThrowUtils.throwIf(request == null || request.getId() == null, ErrorCode.PARAMS_ERROR);
        Corpus corpus = new Corpus();
        BeanUtils.copyProperties(request, corpus);
        boolean result = this.updateById(corpus);
        ThrowUtils.throwIf(!result, ErrorCode.OPERATION_ERROR, "编辑语料失败");
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
        return this.page(new Page<>(current, pageSize), queryWrapper);
    }

    @Override
    public boolean deleteCorpus(Long id) {
        ThrowUtils.throwIf(id == null || id <= 0, ErrorCode.PARAMS_ERROR);
        Corpus corpus = this.getById(id);
        ThrowUtils.throwIf(ObjUtil.isNull(corpus), ErrorCode.NOT_FOUND_ERROR, "语料不存在");
        return this.removeById(id);
    }
}
