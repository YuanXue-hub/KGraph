package com.yuan.seedboot.service.Impl;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.yuan.seedboot.model.entity.RequestLog;
import com.yuan.seedboot.service.RequestLogService;
import com.yuan.seedboot.mapper.RequestLogMapper;
import jakarta.annotation.Resource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

@Service
public class RequestLogServiceImpl extends ServiceImpl<RequestLogMapper, RequestLog>
    implements RequestLogService{

    @Resource
    private JdbcTemplate jdbcTemplate;

    @Override
    public void logRequest(Long userId, Long apiKeyId, String modelName, Integer promptTokens, Integer completionTokens, Integer totalTokens, Integer duration, String status, String errorMessage) {
        RequestLog log = new RequestLog();
        log.setUserId(userId);
        log.setApiKeyId(apiKeyId);
        log.setModelName(modelName);
        log.setPromptTokens(promptTokens != null ? promptTokens : 0);
        log.setCompletionTokens(completionTokens != null ? completionTokens : 0);
        log.setTotalTokens(totalTokens != null ? totalTokens : 0);
        log.setDuration(duration != null ? duration : 0);
        log.setStatus(status != null ? status : "success");
        log.setErrorMessage(errorMessage);
        this.save(log);
    }

    @Override
    public List<RequestLog> listUserLogs(Long userId, Integer limit) {
        QueryWrapper<RequestLog> wrapper = new QueryWrapper<>();
        if (userId != null) {
            wrapper.eq("userId", userId);
        }
        wrapper.orderByDesc("createTime");
        if (limit != null && limit > 0) {
            wrapper.last("LIMIT " + limit);
        }
        return this.list(wrapper);
    }

    @Override
    public Long countUserTokens(Long userId) {
        QueryWrapper<RequestLog> wrapper = new QueryWrapper<>();
        if (userId != null) {
            wrapper.eq("userId", userId);
        }
        wrapper.select("IFNULL(SUM(totalTokens), 0) as total");
        Map<String, Object> result = this.getMap(wrapper);
        if (result == null) return 0L;
        Object total = result.get("total");
        if (total == null) return 0L;
        return ((Number) total).longValue();
    }

    @Override
    public List<Map<String, Object>> getDailyUsage(Long userId, Integer days) {
        int d = (days == null || days <= 0) ? 7 : days;
        StringBuilder sql = new StringBuilder();
        sql.append("SELECT DATE(createTime) AS date, ")
           .append("COUNT(*) AS callCount, ")
           .append("IFNULL(SUM(totalTokens), 0) AS totalTokens, ")
           .append("IFNULL(AVG(duration), 0) AS avgDuration ")
           .append("FROM request_log ")
           .append("WHERE createTime >= DATE_SUB(CURDATE(), INTERVAL ").append(d).append(" DAY) ");
        if (userId != null) {
            sql.append("AND userId = ").append(userId).append(" ");
        }
        sql.append("GROUP BY DATE(createTime) ORDER BY date ASC");
        return jdbcTemplate.queryForList(sql.toString());
    }

    @Override
    public List<Map<String, Object>> getModelUsage(Long userId) {
        StringBuilder sql = new StringBuilder();
        sql.append("SELECT modelName AS modelName, ")
           .append("COUNT(*) AS callCount, ")
           .append("IFNULL(SUM(totalTokens), 0) AS totalTokens, ")
           .append("IFNULL(AVG(duration), 0) AS avgDuration ")
           .append("FROM request_log ");
        if (userId != null) {
            sql.append("WHERE userId = ").append(userId).append(" ");
        }
        sql.append("GROUP BY modelName ORDER BY callCount DESC");
        return jdbcTemplate.queryForList(sql.toString());
    }
}
