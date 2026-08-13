package com.yuan.seedboot.controller;

import com.yuan.seedboot.service.ChatService;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.http.codec.ServerSentEvent;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Flux;

import java.util.Map;

@RestController
@RequestMapping("/v1/chat")
@Slf4j
public class ChatController {

    @Resource
    private ChatService chatService;

    @PostMapping(value = "/agent/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<ServerSentEvent<String>> agentStream(@RequestBody Map<String, Object> body) {
        String message = (String) body.get("message");
        Object modelIdObj = body.get("modelId");
        Long modelId = modelIdObj instanceof Number ? ((Number) modelIdObj).longValue() : null;
        log.info("Chat Agent stream: message={}, modelId={}", message, modelId);
        return chatService.chatAgentStream(message, modelId);
    }
}
