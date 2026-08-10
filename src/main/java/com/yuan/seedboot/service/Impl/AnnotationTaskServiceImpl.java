package com.yuan.seedboot.service.Impl;

import cn.hutool.core.util.ObjUtil;
import cn.hutool.core.util.StrUtil;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.yuan.seedboot.exception.ErrorCode;
import com.yuan.seedboot.exception.ThrowUtils;
import com.yuan.seedboot.mapper.AnnotationTaskMapper;
import com.yuan.seedboot.model.entity.AnnotationTask;
import com.yuan.seedboot.model.entity.User;
import com.yuan.seedboot.model.request.AnnotationTaskAddRequest;
import com.yuan.seedboot.model.request.AnnotationTaskQueryRequest;
import com.yuan.seedboot.model.request.AnnotationTaskUpdateRequest;
import com.yuan.seedboot.service.AnnotationTaskService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Service;

/**
 * @description 针对表【annotation_task(标注任务)】的数据库操作Service实现
 */
@Slf4j
@Service
public class AnnotationTaskServiceImpl extends ServiceImpl<AnnotationTaskMapper, AnnotationTask>
        implements AnnotationTaskService {

    @Override
    public AnnotationTask addAnnotationTask(AnnotationTaskAddRequest request, User loginUser) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        ThrowUtils.throwIf(request.getProjectId() == null, ErrorCode.PARAMS_ERROR, "项目 id 为空");
        ThrowUtils.throwIf(StrUtil.isBlank(request.getTaskName()), ErrorCode.PARAMS_ERROR, "任务名称为空");
        ThrowUtils.throwIf(StrUtil.isBlank(request.getText()), ErrorCode.PARAMS_ERROR, "标注文本为空");
        AnnotationTask annotationTask = new AnnotationTask();
        BeanUtils.copyProperties(request, annotationTask);
        // 按句号分句计算总句数
        annotationTask.setTotalSentences(countSentences(request.getText()));
        annotationTask.setAnnotatedSentences(0);
        annotationTask.setCreateBy(loginUser.getId());
        boolean result = this.save(annotationTask);
        ThrowUtils.throwIf(!result, ErrorCode.OPERATION_ERROR, "新增标注任务失败");
        return annotationTask;
    }

    @Override
    public boolean updateAnnotationTask(AnnotationTaskUpdateRequest request) {
        ThrowUtils.throwIf(request == null || request.getId() == null, ErrorCode.PARAMS_ERROR);
        AnnotationTask annotationTask = new AnnotationTask();
        BeanUtils.copyProperties(request, annotationTask);
        boolean result = this.updateById(annotationTask);
        ThrowUtils.throwIf(!result, ErrorCode.OPERATION_ERROR, "编辑标注任务失败");
        return true;
    }

    @Override
    public Page<AnnotationTask> listAnnotationTask(AnnotationTaskQueryRequest request) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        long current = request.getPageNum();
        long pageSize = request.getPageSize();
        Long projectId = request.getProjectId();
        String taskName = request.getTaskName();
        QueryWrapper<AnnotationTask> queryWrapper = new QueryWrapper<>();
        queryWrapper.eq(ObjUtil.isNotNull(projectId), "projectId", projectId);
        queryWrapper.like(StrUtil.isNotBlank(taskName), "taskName", taskName);
        queryWrapper.orderByDesc("createTime");
        return this.page(new Page<>(current, pageSize), queryWrapper);
    }

    @Override
    public boolean deleteAnnotationTask(Long id) {
        ThrowUtils.throwIf(id == null || id <= 0, ErrorCode.PARAMS_ERROR);
        AnnotationTask annotationTask = this.getById(id);
        ThrowUtils.throwIf(ObjUtil.isNull(annotationTask), ErrorCode.NOT_FOUND_ERROR, "标注任务不存在");
        return this.removeById(id);
    }

    /**
     * 按句号分句计算总句数
     */
    private int countSentences(String text) {
        if (StrUtil.isBlank(text)) {
            return 0;
        }
        // 按中英文句号、问号、感叹号切分
        String[] sentences = text.split("[。！？.!?]+");
        int count = 0;
        for (String sentence : sentences) {
            if (StrUtil.isNotBlank(sentence.trim())) {
                count++;
            }
        }
        return count;
    }
}
