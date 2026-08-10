package com.yuan.seedboot.service;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.IService;
import com.yuan.seedboot.model.entity.AnnotationTask;
import com.yuan.seedboot.model.entity.User;
import com.yuan.seedboot.model.request.AnnotationTaskAddRequest;
import com.yuan.seedboot.model.request.AnnotationTaskQueryRequest;
import com.yuan.seedboot.model.request.AnnotationTaskUpdateRequest;

/**
 * @description 针对表【annotation_task(标注任务)】的数据库操作Service
 */
public interface AnnotationTaskService extends IService<AnnotationTask> {

    /**
     * 新增标注任务
     */
    AnnotationTask addAnnotationTask(AnnotationTaskAddRequest request, User loginUser);

    /**
     * 编辑标注任务（保存标注进度）
     */
    boolean updateAnnotationTask(AnnotationTaskUpdateRequest request);

    /**
     * 分页查询标注任务列表
     */
    Page<AnnotationTask> listAnnotationTask(AnnotationTaskQueryRequest request);

    /**
     * 删除标注任务
     */
    boolean deleteAnnotationTask(Long id);
}
