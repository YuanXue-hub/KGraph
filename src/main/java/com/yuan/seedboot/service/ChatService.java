package com.yuan.seedboot.service;

import org.springframework.http.codec.ServerSentEvent;
import reactor.core.publisher.Flux;

import java.util.Map;

public interface ChatService {
    /**
     * 流式对话 Agent —— 返回 ServerSentEvent 流，保证逐事件即时推送
     */
    Flux<ServerSentEvent<String>> chatAgentStream(String message, Long modelId, String sessionId, Long userId, Long llmModelId);

    java.util.List<Map<String, Object>> listLlmModels();

    /**
     * 可用模型清单（用户隔离：仅自己的）
     */
    java.util.List<Map<String, Object>> listLlmModelsForUser(Long userId);

    /**
     * 模型管理：供应商预设清单
     */
    java.util.List<Map<String, Object>> listLlmProviders();

    /**
     * 模型管理：用户自己的模型列表（key 脱敏）
     */
    java.util.List<Map<String, Object>> listLlmModelsManage(Long userId);

    /**
     * 模型管理：新增模型（归属当前用户）
     */
    Map<String, Object> createLlmModel(Long userId, Map<String, Object> body);

    /**
     * 模型管理：更新模型（仅属主可改）
     */
    Map<String, Object> updateLlmModel(Long userId, Long modelId, Map<String, Object> body);

    /**
     * 模型管理：删除模型（逻辑删除，仅属主可删）
     */
    Map<String, Object> deleteLlmModel(Long userId, Long modelId);

    /**
     * 创建会话 —— 调用 Python 端生成 sessionId
     */
    Map<String, Object> createSession();

    /**
     * 获取用户的历史会话列表
     */
    Map<String, Object> listSessions(Long userId);

    /**
     * 获取会话的完整消息列表
     */
    Map<String, Object> getSessionMessages(String sessionId);

    /**
     * 删除会话（Redis + MySQL 逻辑删除）
     */
    Map<String, Object> deleteSession(String sessionId, Long userId);
}
