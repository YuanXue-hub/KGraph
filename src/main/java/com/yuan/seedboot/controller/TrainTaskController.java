package com.yuan.seedboot.controller;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.yuan.seedboot.common.BaseResponse;
import com.yuan.seedboot.common.DeleteRequest;
import com.yuan.seedboot.common.ResultUtils;
import com.yuan.seedboot.exception.ErrorCode;
import com.yuan.seedboot.exception.ThrowUtils;
import com.yuan.seedboot.model.entity.TrainTask;
import com.yuan.seedboot.model.entity.User;
import com.yuan.seedboot.model.request.TrainTaskAddRequest;
import com.yuan.seedboot.model.request.TrainTaskQueryRequest;
import com.yuan.seedboot.service.TrainTaskService;
import com.yuan.seedboot.service.UserService;
import io.swagger.v3.oas.annotations.Operation;
import jakarta.annotation.Resource;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.web.bind.annotation.*;

/**
 * 训练任务 Controller
 */
@RestController
@RequestMapping("/trainTask")
public class TrainTaskController {

    @Resource
    private TrainTaskService trainTaskService;

    @Resource
    private UserService userService;

    @PostMapping("/add")
    @Operation(summary = "创建并自动开始训练（同步调用 Python，返回完整训练结果）")
    public BaseResponse<TrainTask> addTrainTask(@RequestBody TrainTaskAddRequest request,
                                                HttpServletRequest httpRequest) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        User loginUser = userService.getLoginUser(httpRequest);
        TrainTask trainTask = trainTaskService.createTrainTask(request, loginUser);
        return ResultUtils.success(trainTask);
    }

    @PostMapping("/list")
    @Operation(summary = "训练任务列表（分页）")
    public BaseResponse<Page<TrainTask>> listTrainTask(@RequestBody TrainTaskQueryRequest request) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        Page<TrainTask> page = trainTaskService.listTrainTask(request);
        return ResultUtils.success(page);
    }

    @GetMapping("/get")
    @Operation(summary = "训练任务详情")
    public BaseResponse<TrainTask> getTrainTask(long id) {
        ThrowUtils.throwIf(id <= 0, ErrorCode.PARAMS_ERROR);
        TrainTask trainTask = trainTaskService.getTrainTask(id);
        return ResultUtils.success(trainTask);
    }

    @PostMapping("/delete")
    @Operation(summary = "删除训练任务")
    public BaseResponse<Boolean> deleteTrainTask(@RequestBody DeleteRequest request) {
        ThrowUtils.throwIf(request == null || request.getId() <= 0, ErrorCode.PARAMS_ERROR);
        boolean result = trainTaskService.removeById(request.getId());
        ThrowUtils.throwIf(!result, ErrorCode.OPERATION_ERROR, "删除训练任务失败");
        return ResultUtils.success(result);
    }
}
