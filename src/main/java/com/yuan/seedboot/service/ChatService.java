package com.yuan.seedboot.service;

import org.springframework.http.codec.ServerSentEvent;
import reactor.core.publisher.Flux;

public interface ChatService {
    /**
     * 流式对话 Agent —— 返回 ServerSentEvent 流，保证逐事件即时推送
     */
    Flux<ServerSentEvent<String>> chatAgentStream(String message, Long modelId);
}
