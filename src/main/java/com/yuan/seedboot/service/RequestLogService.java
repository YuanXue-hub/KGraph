package com.yuan.seedboot.service;

import com.yuan.seedboot.model.entity.RequestLog;
import com.baomidou.mybatisplus.extension.service.IService;

import java.util.List;

/**
* @author Yuan
* @description 针对表【request_log(请求日志)】的数据库操作Service
* @createDate 2026-06-13 22:41:01
*/
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
}

