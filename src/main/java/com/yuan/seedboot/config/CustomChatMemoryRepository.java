package com.yuan.seedboot.config;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.yuan.seedboot.mapper.ChatHistoryMapper;
import com.yuan.seedboot.model.entity.ChatHistory;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.ai.chat.memory.ChatMemoryRepository;
import org.springframework.ai.chat.messages.AssistantMessage;
import org.springframework.ai.chat.messages.Message;
import org.springframework.ai.chat.messages.UserMessage;
import org.springframework.stereotype.Repository;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Date;
import java.util.List;
import java.util.stream.Collectors;

@Slf4j
@Repository
public class CustomChatMemoryRepository implements ChatMemoryRepository {

    @Resource
    private ChatHistoryMapper chatHistoryMapper;

    @Override
    public List<String> findConversationIds() {
        LambdaQueryWrapper<ChatHistory> wrapper = Wrappers.<ChatHistory>lambdaQuery()
                .select(ChatHistory::getSessionId)
                .eq(ChatHistory::getIsDelete, 0)
                .groupBy(ChatHistory::getSessionId);

        List<ChatHistory> histories = chatHistoryMapper.selectList(wrapper);
        return histories.stream()
                .map(ChatHistory::getSessionId)  // 直接返回 String，不需要转换
                .distinct()
                .collect(Collectors.toList());
    }

    @Override
    public List<Message> findByConversationId(String conversationId) {
        // ✅ 关键修改：不再转换为 Long，直接使用 String
        LambdaQueryWrapper<ChatHistory> wrapper = Wrappers.<ChatHistory>lambdaQuery()
                .eq(ChatHistory::getSessionId, conversationId)  // 直接使用 String
                .eq(ChatHistory::getIsDelete, 0)
                .orderByAsc(ChatHistory::getCreateTime);

        List<ChatHistory> histories = chatHistoryMapper.selectList(wrapper);

        if (histories.isEmpty()) {
            return Collections.emptyList();
        }

        return histories.stream()
                .map(this::convertToAiMessage)
                .collect(Collectors.toList());
    }

    @Override
    public void saveAll(String conversationId, List<Message> messages) {
        log.info("=== saveAll 被调用 ===");
        log.info("会话ID: {}", conversationId);
        log.info("消息数量: {}", messages.size());
        log.info("消息内容: {}", messages.stream().map(Message::getText).collect(Collectors.joining("|")));
        log.info("调用时间: {}", new Date());

        // 打印调用堆栈，看看是谁调用的
        StackTraceElement[] stackTrace = Thread.currentThread().getStackTrace();
        for (int i = 0; i < Math.min(10, stackTrace.length); i++) {
            log.info("调用栈[{}]: {}", i, stackTrace[i]);
        }

        if (messages == null || messages.isEmpty()) {
            return;
        }

        Long userId = getCurrentUserId();

        Message message = messages.get(messages.size() - 1);
        ChatHistory history = new ChatHistory();
        history.setSessionId(conversationId);  // ✅ 直接使用 String
        history.setUserId(userId);
        history.setMessage(message.getText());
        history.setMessageType(getMessageType(message));
        history.setIsDelete(0);
        history.setCreateTime(new Date());
        history.setUpdateTime(new Date());

        chatHistoryMapper.insert(history);

        log.debug("已保存 {} 条消息到会话 {}", messages.size(), conversationId);
    }

    @Override
    public void deleteByConversationId(String conversationId) {
        LambdaQueryWrapper<ChatHistory> wrapper = Wrappers.<ChatHistory>lambdaQuery()
                .eq(ChatHistory::getSessionId, conversationId);

        ChatHistory updateEntity = new ChatHistory();
        updateEntity.setIsDelete(1);

        chatHistoryMapper.update(updateEntity, wrapper);
        log.info("已删除会话 {} 的历史记录", conversationId);
    }

    // ==================== 辅助方法 ====================

    private Message convertToAiMessage(ChatHistory history) {
        String messageType = history.getMessageType();
        String content = history.getMessage();

        if ("user".equalsIgnoreCase(messageType)) {
            return new UserMessage(content);
        } else if ("ai".equalsIgnoreCase(messageType)) {
            return new AssistantMessage(content);
        } else {
            return new UserMessage(content);
        }
    }

    private String getMessageType(Message message) {
        switch (message.getMessageType()) {
            case USER:
                return "user";
            case ASSISTANT:
                return "ai";
            default:
                return "user";
        }
    }

    private Long getCurrentUserId() {
        // TODO: 从 SecurityContext 获取
        return 1L;
    }
}