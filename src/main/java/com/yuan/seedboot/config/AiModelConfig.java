package com.yuan.seedboot.config;

import com.yuan.seedboot.config.CustomChatMemoryRepository;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.client.advisor.MessageChatMemoryAdvisor;
import org.springframework.ai.chat.memory.ChatMemory;
import org.springframework.ai.chat.memory.MessageWindowChatMemory;
import org.springframework.ai.openai.OpenAiChatOptions;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;

@Slf4j
@Configuration
public class AiModelConfig {

    @Resource
    private CustomChatMemoryRepository customRepository;

    /**
     * 配置 ChatMemory（MySQL 持久化）
     */
    @Bean
    public ChatMemory mysqlChatMemory() {
        return MessageWindowChatMemory.builder()
                .chatMemoryRepository(customRepository)
                .maxMessages(30)
                .build();
    }

    /**
     * 配置带记忆功能的 ChatClient
     * 使用 Spring Boot 自动配置的 Builder，更简洁
     */
    @Bean
    @Primary
    public ChatClient deepSeekChatClient(ChatClient.Builder builder, ChatMemory mysqlChatMemory) {
        MessageChatMemoryAdvisor memoryAdvisor = MessageChatMemoryAdvisor
                .builder(mysqlChatMemory)
                .build();

        return builder
                .defaultAdvisors(memoryAdvisor)
                .defaultOptions(OpenAiChatOptions.builder()
                        .temperature(0.7)
                        .maxTokens(2000)
                        .build())
                .build();
    }
}