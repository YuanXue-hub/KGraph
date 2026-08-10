package com.yuan.seedboot.service.Impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.yuan.seedboot.model.entity.RequestLog;
import com.yuan.seedboot.service.RequestLogService;
import com.yuan.seedboot.mapper.RequestLogMapper;
import org.springframework.stereotype.Service;

import java.util.List;

/**
* @author Yuan
* @description 针对表【request_log(请求日志)】的数据库操作Service实现
* @createDate 2026-06-13 22:41:01
*/
@Service
public class RequestLogServiceImpl extends ServiceImpl<RequestLogMapper, RequestLog>
    implements RequestLogService{

    @Override
    public void logRequest(Long userId, Long apiKeyId, String modelName, Integer promptTokens, Integer completionTokens, Integer totalTokens, Integer duration, String status, String errorMessage) {

    }

    @Override
    public List<RequestLog> listUserLogs(Long userId, Integer limit) {
        return List.of();
    }

    @Override
    public Long countUserTokens(Long userId) {
        return 0L;
    }
}




