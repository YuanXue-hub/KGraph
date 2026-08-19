package com.yuan.seedboot.service;

import org.springframework.http.codec.ServerSentEvent;
import reactor.core.publisher.Flux;

import java.util.Map;

public interface ChatService {
    /**
     * 流式对话 Agent —— 返回 ServerSentEvent 流，保证逐事件即时推送
     */
    Flux<ServerSentEvent<String>> chatAgentStream(String message, Long modelId, String sessionId, Long userId);

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
