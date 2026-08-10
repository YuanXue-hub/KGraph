package com.yuan.seedboot.controller;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.yuan.seedboot.common.BaseResponse;
import com.yuan.seedboot.common.DeleteRequest;
import com.yuan.seedboot.common.ResultUtils;
import com.yuan.seedboot.exception.ErrorCode;
import com.yuan.seedboot.exception.ThrowUtils;
import com.yuan.seedboot.model.entity.AnnotationTask;
import com.yuan.seedboot.model.entity.User;
import com.yuan.seedboot.model.request.AnnotationTaskAddRequest;
import com.yuan.seedboot.model.request.AnnotationTaskQueryRequest;
import com.yuan.seedboot.model.request.AnnotationTaskUpdateRequest;
import com.yuan.seedboot.service.AnnotationTaskService;
import com.yuan.seedboot.service.UserService;
import io.swagger.v3.oas.annotations.Operation;
import jakarta.annotation.Resource;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.web.bind.annotation.*;

/**
 * 标注任务 Controller
 */
@RestController
@RequestMapping("/annotationTask")
public class AnnotationTaskController {

    @Resource
    private AnnotationTaskService annotationTaskService;

    @Resource
    private UserService userService;

    @PostMapping("/add")
    @Operation(summary = "新增标注任务")
    public BaseResponse<AnnotationTask> addAnnotationTask(@RequestBody AnnotationTaskAddRequest request,
                                                          HttpServletRequest httpRequest) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        User loginUser = userService.getLoginUser(httpRequest);
        AnnotationTask annotationTask = annotationTaskService.addAnnotationTask(request, loginUser);
        return ResultUtils.success(annotationTask);
    }

    @PostMapping("/update")
    @Operation(summary = "编辑标注任务（保存标注进度）")
    public BaseResponse<Boolean> updateAnnotationTask(@RequestBody AnnotationTaskUpdateRequest request) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        boolean result = annotationTaskService.updateAnnotationTask(request);
        return ResultUtils.success(result);
    }

    @PostMapping("/delete")
    @Operation(summary = "删除标注任务")
    public BaseResponse<Boolean> deleteAnnotationTask(@RequestBody DeleteRequest request) {
        ThrowUtils.throwIf(request == null || request.getId() <= 0, ErrorCode.PARAMS_ERROR);
        boolean result = annotationTaskService.deleteAnnotationTask(request.getId());
        return ResultUtils.success(result);
    }

    @GetMapping("/list")
    @Operation(summary = "标注任务列表（分页）")
    public BaseResponse<Page<AnnotationTask>> listAnnotationTask(AnnotationTaskQueryRequest request) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        Page<AnnotationTask> page = annotationTaskService.listAnnotationTask(request);
        return ResultUtils.success(page);
    }

    @GetMapping("/get")
    @Operation(summary = "标注任务详情")
    public BaseResponse<AnnotationTask> getAnnotationTask(long id) {
        ThrowUtils.throwIf(id <= 0, ErrorCode.PARAMS_ERROR);
        AnnotationTask annotationTask = annotationTaskService.getById(id);
        ThrowUtils.throwIf(annotationTask == null, ErrorCode.NOT_FOUND_ERROR);
        return ResultUtils.success(annotationTask);
    }
}
