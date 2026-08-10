package com.yuan.seedboot.service.Impl;

import cn.hutool.core.util.IdUtil;
import cn.hutool.json.JSONObject;
import com.baomidou.mybatisplus.core.toolkit.ObjectUtils;
import com.yuan.seedboot.exception.BusinessException;
import com.yuan.seedboot.exception.ErrorCode;
import com.yuan.seedboot.model.dto.ChatMessage;
import com.yuan.seedboot.model.dto.ChatRequest;
import com.yuan.seedboot.model.dto.ChatResponse;
import com.yuan.seedboot.service.ChatService;
import com.yuan.seedboot.service.RequestLogService;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.messages.AssistantMessage;
import org.springframework.ai.chat.messages.Message;
import org.springframework.ai.chat.messages.SystemMessage;
import org.springframework.ai.chat.messages.UserMessage;
import org.springframework.ai.chat.model.ChatModel;

import org.springframework.ai.chat.prompt.Prompt;
import org.springframework.ai.openai.OpenAiChatOptions;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Flux;

import java.util.List;
import java.util.stream.Collectors;

@Slf4j
@Service
public class ChatServiceImpl implements ChatService {

    @Resource
    private ChatClient deepSeekChatClient;

    @Override
    public ChatResponse chat(String userInput, Long userId) {
        return null;
    }

    @Override
    public Flux<String> chatStream(String userInput, Long userId) {
        return deepSeekChatClient
                .prompt()
                .system("AI助手")
                .user(userInput)
                .advisors(advisor -> advisor
                        .param("chat_memory_conversation_id", "session_1"))  //
                .stream()
                .chatResponse()
                .map(chunk -> {
                    String text = chunk.getResult().getOutput().getText();
                    JSONObject entries = new JSONObject();
                    entries.set("ai", text);
                    return entries.toString();
                })
                .doOnComplete(() -> {
                    log.info("输出已完成");
                });
    }
}
