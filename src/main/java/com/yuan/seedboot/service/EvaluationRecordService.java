package com.yuan.seedboot.service;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.IService;
import com.yuan.seedboot.common.PageRequest;
import com.yuan.seedboot.model.entity.EvaluationRecord;

/**
 * @description 针对表【evaluation_record(评估历史)】的数据库操作Service
 */
public interface EvaluationRecordService extends IService<EvaluationRecord> {

    /**
     * 分页查询某抽取任务的评估历史（时间倒序，不含 result 大字段）
     */
    Page<EvaluationRecord> listByTaskId(Long taskId, PageRequest pageRequest);
}
