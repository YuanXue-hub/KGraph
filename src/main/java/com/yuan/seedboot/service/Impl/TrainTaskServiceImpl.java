package com.yuan.seedboot.service.Impl;

import cn.hutool.core.util.ObjUtil;
import cn.hutool.core.util.StrUtil;
import cn.hutool.json.JSONObject;
import cn.hutool.json.JSONUtil;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.yuan.seedboot.config.PythonServiceClient;
import com.yuan.seedboot.exception.BusinessException;
import com.yuan.seedboot.exception.ErrorCode;
import com.yuan.seedboot.exception.ThrowUtils;
import com.yuan.seedboot.mapper.TrainTaskMapper;
import com.yuan.seedboot.model.entity.AnnotationTask;
import com.yuan.seedboot.model.entity.TrainTask;
import com.yuan.seedboot.model.entity.User;
import com.yuan.seedboot.model.request.TrainTaskAddRequest;
import com.yuan.seedboot.model.request.TrainTaskQueryRequest;
import com.yuan.seedboot.service.AnnotationTaskService;
import com.yuan.seedboot.service.TrainTaskService;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.Map;

/**
 * @description 针对表【train_task(训练任务)】的数据库操作Service实现
 */
@Slf4j
@Service
public class TrainTaskServiceImpl extends ServiceImpl<TrainTaskMapper, TrainTask>
        implements TrainTaskService {

    @Resource
    private PythonServiceClient pythonServiceClient;

    @Resource
    private AnnotationTaskService annotationTaskService;

    @Override
    public TrainTask createTrainTask(TrainTaskAddRequest request, User loginUser) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        ThrowUtils.throwIf(request.getProjectId() == null, ErrorCode.PARAMS_ERROR, "项目 id 为空");
        ThrowUtils.throwIf(request.getAnnotationTaskId() == null, ErrorCode.PARAMS_ERROR, "标注任务 id 为空");
        ThrowUtils.throwIf(StrUtil.isBlank(request.getTaskName()), ErrorCode.PARAMS_ERROR, "任务名称为空");

        TrainTask trainTask = new TrainTask();
        BeanUtils.copyProperties(request, trainTask);
        trainTask.setStatus("pending");
        trainTask.setProgress(0);
        trainTask.setCurrentEpoch(0);
        trainTask.setEpochs(ObjUtil.defaultIfNull(request.getEpochs(), 10));
        // 版本号：1.任务数
        long taskCount = this.count();
        trainTask.setVersion("1." + taskCount);
        // 保存训练配置
        trainTask.setConfig(buildTrainConfig(request));
        trainTask.setCreateBy(loginUser.getId());
        boolean saved = this.save(trainTask);
        ThrowUtils.throwIf(!saved, ErrorCode.OPERATION_ERROR, "创建训练任务失败");

        // 创建完成后自动开始训练
        return startTrain(trainTask.getId());
    }

    @Override
    public TrainTask startTrain(Long taskId) {
        ThrowUtils.throwIf(taskId == null || taskId <= 0, ErrorCode.PARAMS_ERROR);
        TrainTask trainTask = this.getById(taskId);
        ThrowUtils.throwIf(ObjUtil.isNull(trainTask), ErrorCode.NOT_FOUND_ERROR, "训练任务不存在");

        // a. 设置 status=training, 保存
        trainTask.setStatus("training");
        boolean updated = this.updateById(trainTask);
        ThrowUtils.throwIf(!updated, ErrorCode.OPERATION_ERROR, "更新训练任务状态失败");

        try {
            // b. 从 annotationTaskId 获取标注数据(entities/relations)
            AnnotationTask annotationTask = annotationTaskService.getById(trainTask.getAnnotationTaskId());
            ThrowUtils.throwIf(ObjUtil.isNull(annotationTask), ErrorCode.NOT_FOUND_ERROR, "标注任务不存在");
            Map<String, Object> annotationData = new HashMap<>();
            annotationData.put("entities", parseJson(annotationTask.getEntities()));
            annotationData.put("relations", parseJson(annotationTask.getRelations()));
            annotationData.put("text", annotationTask.getText());

            // c. 调用 pythonServiceClient.train
            Map<String, Object> trainConfig = new HashMap<>();
            trainConfig.put("dataset", trainTask.getDataset());
            trainConfig.put("architecture", trainTask.getArchitecture());
            trainConfig.put("epochs", trainTask.getEpochs());
            trainConfig.put("version", trainTask.getVersion());

            JSONObject resp = pythonServiceClient.train(annotationData, trainConfig, null);

            // d. 解析返回的 history/metrics, 设置到任务
            Object history = resp.get("history");
            Object metrics = resp.get("metrics");
            trainTask.setHistory(history == null ? null : JSONUtil.toJsonStr(history));
            trainTask.setMetrics(metrics == null ? null : JSONUtil.toJsonStr(metrics));

            // e. status=done, progress=100, currentEpoch=epochs
            trainTask.setStatus("done");
            trainTask.setProgress(100);
            trainTask.setCurrentEpoch(trainTask.getEpochs());
        } catch (Exception e) {
            log.error("训练任务执行失败, taskId={}", taskId, e);
            trainTask.setStatus("failed");
            this.updateById(trainTask);
            throw e instanceof BusinessException ? (BusinessException) e
                    : new BusinessException(ErrorCode.OPERATION_ERROR, "训练任务执行失败: " + e.getMessage());
        }
        // f. updateById 保存, 返回任务
        this.updateById(trainTask);
        return trainTask;
    }

    @Override
    public Page<TrainTask> listTrainTask(TrainTaskQueryRequest request) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        long current = request.getPageNum();
        long pageSize = request.getPageSize();
        Long projectId = request.getProjectId();
        String status = request.getStatus();
        String architecture = request.getArchitecture();
        QueryWrapper<TrainTask> queryWrapper = new QueryWrapper<>();
        queryWrapper.eq(ObjUtil.isNotNull(projectId), "projectId", projectId);
        queryWrapper.eq(StrUtil.isNotBlank(status), "status", status);
        queryWrapper.eq(StrUtil.isNotBlank(architecture), "architecture", architecture);
        queryWrapper.orderByDesc("createTime");
        return this.page(new Page<>(current, pageSize), queryWrapper);
    }

    @Override
    public TrainTask getTrainTask(Long id) {
        ThrowUtils.throwIf(id == null || id <= 0, ErrorCode.PARAMS_ERROR);
        TrainTask trainTask = this.getById(id);
        ThrowUtils.throwIf(ObjUtil.isNull(trainTask), ErrorCode.NOT_FOUND_ERROR, "训练任务不存在");
        return trainTask;
    }

    /**
     * 构建训练配置 JSON 字符串
     */
    private String buildTrainConfig(TrainTaskAddRequest request) {
        Map<String, Object> config = new HashMap<>();
        config.put("dataset", request.getDataset());
        config.put("architecture", request.getArchitecture());
        config.put("epochs", ObjUtil.defaultIfNull(request.getEpochs(), 10));
        return JSONUtil.toJsonStr(config);
    }

    /**
     * 解析 JSON 字符串为对象，空字符串返回 null
     */
    private Object parseJson(String json) {
        if (StrUtil.isBlank(json)) {
            return null;
        }
        try {
            return JSONUtil.parse(json);
        } catch (Exception e) {
            log.warn("解析 JSON 失败: {}", json, e);
            return json;
        }
    }
}
