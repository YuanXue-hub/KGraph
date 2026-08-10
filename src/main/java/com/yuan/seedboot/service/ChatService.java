package com.yuan.seedboot.service;

import com.yuan.seedboot.model.dto.ChatRequest;
import com.yuan.seedboot.model.dto.ChatResponse;
import reactor.core.publisher.Flux;

public interface ChatService {

    /**
     * 非流式对话
     */
    ChatResponse chat(String userInput, Long userId);

    /**
     *  流式对话
     */
    Flux<String> chatStream(String userInput, Long userId);
}
