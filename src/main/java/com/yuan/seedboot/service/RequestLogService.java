package com.yuan.seedboot.service;

import com.yuan.seedboot.model.entity.RequestLog;
import com.baomidou.mybatisplus.extension.service.IService;

import java.util.List;
import java.util.Map;

public interface RequestLogService extends IService<RequestLog> {
    /**
     * 记录请求日志
     */
    void logRequest(Long userId, Long apiKeyId, String modelName,
                    Integer promptTokens, Integer completionTokens, Integer totalTokens,
                    Integer duration, String status, String errorMessage);

    /**
     * 查询用户的请求日志
     */
    List<RequestLog> listUserLogs(Long userId, Integer limit);

    /**
     * 统计用户的 Token 消耗
     */
    Long countUserTokens(Long userId);

    /**
     * 查询用户最近 N 天的用量统计（按天聚合：调用次数、Token 消耗）
     */
    List<Map<String, Object>> getDailyUsage(Long userId, Integer days);

    /**
     * 查询用户各模型的用量统计（按模型聚合）
     */
    List<Map<String, Object>> getModelUsage(Long userId);
}

