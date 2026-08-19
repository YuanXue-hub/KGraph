package com.yuan.seedboot.controller;

import com.yuan.seedboot.model.entity.User;
import com.yuan.seedboot.service.ChatService;
import com.yuan.seedboot.service.UserService;
import jakarta.annotation.Resource;
import jakarta.servlet.http.HttpServletRequest;
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

    @Resource
    private UserService userService;

    /**
     * 创建会话 —— 返回 sessionId
     */
    @PostMapping("/session/create")
    public Map<String, Object> createSession() {
        log.info("Create chat session request");
        return chatService.createSession();
    }

    /**
     * 获取当前登录用户的历史会话列表（用户间隔离）
     */
    @GetMapping("/session/list")
    public Map<String, Object> listSessions(HttpServletRequest httpRequest) {
        User loginUser = userService.getLoginUser(httpRequest);
        log.info("List chat sessions: userId={}", loginUser.getId());
        return chatService.listSessions(loginUser.getId());
    }

    /**
     * 获取会话的完整消息列表（切换页面后恢复历史对话）
     */
    @GetMapping("/session/{sessionId}/messages")
    public Map<String, Object> getSessionMessages(@PathVariable String sessionId) {
        return chatService.getSessionMessages(sessionId);
    }

    /**
     * 删除会话（清除 Redis + MySQL 逻辑删除，仅允许删除自己的会话）
     */
    @DeleteMapping("/session/{sessionId}")
    public Map<String, Object> deleteSession(@PathVariable String sessionId, HttpServletRequest httpRequest) {
        User loginUser = userService.getLoginUser(httpRequest);
        log.info("Delete chat session: sessionId={}, userId={}", sessionId, loginUser.getId());
        return chatService.deleteSession(sessionId, loginUser.getId());
    }

    /**
     * 流式对话 Agent（SSE）
     */
    @PostMapping(value = "/agent/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<ServerSentEvent<String>> agentStream(@RequestBody Map<String, Object> body, HttpServletRequest httpRequest) {
        User loginUser = userService.getLoginUser(httpRequest);
        String message = (String) body.get("message");
        Object modelIdObj = body.get("modelId");
        Long modelId = null;
        if (modelIdObj instanceof Number) {
            modelId = ((Number) modelIdObj).longValue();
        } else if (modelIdObj instanceof String s && !s.isBlank()) {
            // 前端拿到的模型 id 是 Jackson 全局 Long→String 序列化后的字符串，需兼容
            try {
                modelId = Long.parseLong(s);
            } catch (NumberFormatException ignored) {
            }
        }
        Object sessionIdObj = body.get("sessionId");
        String sessionId = sessionIdObj != null ? String.valueOf(sessionIdObj) : null;
        log.info("Chat Agent stream: message={}, modelId={}, sessionId={}, userId={}", message, modelId, sessionId, loginUser.getId());
        return chatService.chatAgentStream(message, modelId, sessionId, loginUser.getId());
    }
}
