package com.yuan.seedboot.controller;

import com.yuan.seedboot.model.entity.User;
import com.yuan.seedboot.service.ChatService;
import com.yuan.seedboot.service.RequestLogService;
import com.yuan.seedboot.service.UserService;
import jakarta.annotation.Resource;
import jakarta.servlet.http.HttpServletRequest;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.http.codec.ServerSentEvent;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Flux;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/v1/chat")
@Slf4j
public class ChatController {

    @Resource
    private ChatService chatService;

    @Resource
    private UserService userService;

    @Resource
    private RequestLogService requestLogService;

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
        Long llmModelId = parseLongField(body.get("llmModelId"));
        log.info("Chat Agent stream: message={}, modelId={}, sessionId={}, userId={}, llmModelId={}",
                message, modelId, sessionId, loginUser.getId(), llmModelId);
        return chatService.chatAgentStream(message, modelId, sessionId, loginUser.getId(), llmModelId);
    }

    /**
     * 可用 LLM 模型清单（供前端问答/抽取/评估选择，用户隔离：仅自己的）
     */
    @GetMapping("/llm-models")
    public java.util.List<Map<String, Object>> listLlmModels(HttpServletRequest httpRequest) {
        User loginUser = userService.getLoginUser(httpRequest);
        return chatService.listLlmModelsForUser(loginUser.getId());
    }

    /**
     * 模型管理：供应商预设清单
     */
    @GetMapping("/llm-providers")
    public java.util.List<Map<String, Object>> listLlmProviders() {
        return chatService.listLlmProviders();
    }

    /**
     * 模型管理：模型列表（用户隔离，key 脱敏）
     */
    @GetMapping("/llm-models/manage")
    public java.util.List<Map<String, Object>> listLlmModelsManage(HttpServletRequest httpRequest) {
        User loginUser = userService.getLoginUser(httpRequest);
        return chatService.listLlmModelsManage(loginUser.getId());
    }

    /**
     * 模型管理：新增模型（归属当前用户）
     */
    @PostMapping("/llm-models/manage")
    public Map<String, Object> createLlmModel(@RequestBody Map<String, Object> body, HttpServletRequest httpRequest) {
        User loginUser = userService.getLoginUser(httpRequest);
        return chatService.createLlmModel(loginUser.getId(), body);
    }

    /**
     * 模型管理：更新模型（仅属主可改）
     */
    @PutMapping("/llm-models/manage/{modelId}")
    public Map<String, Object> updateLlmModel(@PathVariable Long modelId, @RequestBody Map<String, Object> body,
                                              HttpServletRequest httpRequest) {
        User loginUser = userService.getLoginUser(httpRequest);
        return chatService.updateLlmModel(loginUser.getId(), modelId, body);
    }

    /**
     * 模型管理：删除模型（逻辑删除，仅属主可删）
     */
    @DeleteMapping("/llm-models/manage/{modelId}")
    public Map<String, Object> deleteLlmModel(@PathVariable Long modelId, HttpServletRequest httpRequest) {
        User loginUser = userService.getLoginUser(httpRequest);
        return chatService.deleteLlmModel(loginUser.getId(), modelId);
    }

    private Long parseLongField(Object obj) {
        if (obj instanceof Number) {
            return ((Number) obj).longValue();
        }
        if (obj instanceof String s && !s.isBlank()) {
            try {
                return Long.parseLong(s);
            } catch (NumberFormatException ignored) {
            }
        }
        return null;
    }

    /**
     * LLM 用量统计概览（总调用次数、总 Token 消耗、最近 7 天每日趋势、各模型分布）
     */
    @GetMapping("/usage")
    public Map<String, Object> getUsage(@RequestParam(defaultValue = "7") Integer days,
                                        HttpServletRequest httpRequest) {
        User loginUser = userService.getLoginUser(httpRequest);
        Long userId = loginUser.getId();
        Map<String, Object> result = new HashMap<>();
        // 总调用次数
        long totalCalls = requestLogService.lambdaQuery()
                .eq(com.yuan.seedboot.model.entity.RequestLog::getUserId, userId)
                .count();
        // 总 Token 消耗
        long totalTokens = requestLogService.countUserTokens(userId);
        // 每日趋势
        List<Map<String, Object>> daily = requestLogService.getDailyUsage(userId, days);
        // 各模型分布
        List<Map<String, Object>> byModel = requestLogService.getModelUsage(userId);
        result.put("totalCalls", totalCalls);
        result.put("totalTokens", totalTokens);
        result.put("daily", daily);
        result.put("byModel", byModel);
        return result;
    }
}
