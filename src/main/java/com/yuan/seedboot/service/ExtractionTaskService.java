package com.yuan.seedboot.service;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.IService;
import com.yuan.seedboot.common.PageRequest;
import com.yuan.seedboot.model.entity.ExtractionTask;
import com.yuan.seedboot.model.entity.User;
import com.yuan.seedboot.model.request.ExtractionDlRequest;
import com.yuan.seedboot.model.request.ExtractionKosRequest;
import com.yuan.seedboot.model.request.ExtractionRequest;

/**
 * @description 针对表【extraction_task(抽取任务)】的数据库操作Service
 */
public interface ExtractionTaskService extends IService<ExtractionTask> {

    /**
     * 创建 LLM 抽取任务并调用 Python 执行抽取
     */
    ExtractionTask createExtraction(ExtractionRequest request, User loginUser);

    /**
     * 创建 KOS 抽取任务并调用 Python 执行抽取
     */
    ExtractionTask createKosExtraction(ExtractionKosRequest request, User loginUser);

    /**
     * 创建深度学习抽取任务并调用 Python 执行抽取
     */
    ExtractionTask createDlExtraction(ExtractionDlRequest request, User loginUser);

    /**
     * 分页查询抽取任务列表
     */
    Page<ExtractionTask> listExtractionTasks(Long projectId, String extractionType, PageRequest pageRequest);

    /**
     * 获取抽取任务详情
     */
    ExtractionTask getExtractionTask(Long id);
}
