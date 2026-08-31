package com.yuan.seedboot.service.Impl;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.yuan.seedboot.common.PageRequest;
import com.yuan.seedboot.exception.ErrorCode;
import com.yuan.seedboot.exception.ThrowUtils;
import com.yuan.seedboot.mapper.EvaluationRecordMapper;
import com.yuan.seedboot.model.entity.EvaluationRecord;
import com.yuan.seedboot.service.EvaluationRecordService;
import org.springframework.stereotype.Service;

@Service
public class EvaluationRecordServiceImpl extends ServiceImpl<EvaluationRecordMapper, EvaluationRecord>
        implements EvaluationRecordService {

    @Override
    public Page<EvaluationRecord> listByTaskId(Long taskId, PageRequest pageRequest) {
        ThrowUtils.throwIf(pageRequest == null, ErrorCode.PARAMS_ERROR);
        QueryWrapper<EvaluationRecord> wrapper = new QueryWrapper<>();
        wrapper.eq(taskId != null && taskId > 0, "taskId", taskId)
                .select("id", "taskId", "sampleSize", "overall", "tokenConsumed", "duration", "createBy", "createTime")
                .orderByDesc("createTime");
        return this.page(new Page<>(pageRequest.getPageNum(), pageRequest.getPageSize()), wrapper);
    }
}
