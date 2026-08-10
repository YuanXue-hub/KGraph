package com.yuan.seedboot.controller;

import com.yuan.seedboot.service.ChatService;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Flux;

@RestController
@RequestMapping("/v1/chat")
@Slf4j
public class ChatController {

    @Resource
    private ChatService chatService;

    @GetMapping("/chat")
    public String chat(@RequestParam String message){
        return null;
    }

    @PostMapping(value = "/chat/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<String> stream(@RequestParam String message){
        return chatService.chatStream(message, 1l);
    }
}
