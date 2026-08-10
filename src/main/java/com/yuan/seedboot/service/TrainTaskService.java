package com.yuan.seedboot.service;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.IService;
import com.yuan.seedboot.model.entity.TrainTask;
import com.yuan.seedboot.model.entity.User;
import com.yuan.seedboot.model.request.TrainTaskAddRequest;
import com.yuan.seedboot.model.request.TrainTaskQueryRequest;

/**
 * @description 针对表【train_task(训练任务)】的数据库操作Service
 */
public interface TrainTaskService extends IService<TrainTask> {

    /**
     * 创建训练任务并自动开始训练
     */
    TrainTask createTrainTask(TrainTaskAddRequest request, User loginUser);

    /**
     * 开始训练（同步调用 Python，返回完整训练结果）
     */
    TrainTask startTrain(Long taskId);

    /**
     * 分页查询训练任务列表
     */
    Page<TrainTask> listTrainTask(TrainTaskQueryRequest request);

    /**
     * 查询训练任务详情
     */
    TrainTask getTrainTask(Long id);
}
