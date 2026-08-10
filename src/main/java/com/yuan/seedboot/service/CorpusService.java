package com.yuan.seedboot.service;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.IService;
import com.yuan.seedboot.model.entity.Corpus;
import com.yuan.seedboot.model.entity.User;
import com.yuan.seedboot.model.request.CorpusAddRequest;
import com.yuan.seedboot.model.request.CorpusQueryRequest;
import com.yuan.seedboot.model.request.CorpusUpdateRequest;

/**
 * @description 针对表【corpus(语料)】的数据库操作Service
 */
public interface CorpusService extends IService<Corpus> {

    /**
     * 新增语料
     */
    Corpus addCorpus(CorpusAddRequest request, User loginUser);

    /**
     * 编辑语料
     */
    boolean updateCorpus(CorpusUpdateRequest request);

    /**
     * 分页查询语料列表
     */
    Page<Corpus> listCorpus(CorpusQueryRequest request);

    /**
     * 删除语料
     */
    boolean deleteCorpus(Long id);
}
