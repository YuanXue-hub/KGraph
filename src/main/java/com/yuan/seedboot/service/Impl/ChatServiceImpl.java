package com.yuan.seedboot.service.Impl;

import com.yuan.seedboot.service.ChatService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.MediaType;
import org.springframework.http.codec.ServerSentEvent;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;

import java.time.Duration;
import java.util.HashMap;
import java.util.Map;

@Slf4j
@Service
public class ChatServiceImpl implements ChatService {

    private final WebClient webClient;

    @Value("${python.service.url:http://localhost:8001}")
    private String pythonServiceUrl;

    public ChatServiceImpl(WebClient.Builder webClientBuilder) {
        this.webClient = webClientBuilder
                .codecs(configurer -> configurer.defaultCodecs().maxInMemorySize(16 * 1024 * 1024))
                .build();
    }

    @Override
    public Flux<ServerSentEvent<String>> chatAgentStream(String message, Long modelId, String sessionId, Long userId) {
        Map<String, Object> payload = new HashMap<>();
        payload.put("message", message);
        payload.put("modelId", modelId != null ? modelId : 0);
        if (sessionId != null) {
            payload.put("sessionId", sessionId);
        }
        if (userId != null) {
            payload.put("userId", userId);
        }

        String targetUrl = pythonServiceUrl + "/api/chat/agent/stream";
        log.info("Chat Agent SSE proxy: url={}, modelId={}, sessionId={}, userId={}", targetUrl, modelId, sessionId, userId);

        ParameterizedTypeReference<ServerSentEvent<String>> sseType =
                new ParameterizedTypeReference<>() {};

        return webClient.post()
                .uri(targetUrl)
                .contentType(MediaType.APPLICATION_JSON)
                .accept(MediaType.TEXT_EVENT_STREAM)
                .bodyValue(payload)
                .retrieve()
                .bodyToFlux(sseType)
                .timeout(Duration.ofSeconds(60))
                .doOnError(e -> log.error("Chat Agent SSE proxy error", e))
                .doOnComplete(() -> log.info("Chat Agent SSE proxy stream completed"));
    }

    @Override
    @SuppressWarnings("unchecked")
    public Map<String, Object> createSession() {
        String targetUrl = pythonServiceUrl + "/api/chat/session/create";
        return webClient.post()
                .uri(targetUrl)
                .retrieve()
                .bodyToMono(Map.class)
                .timeout(Duration.ofSeconds(10))
                .block();
    }

    @Override
    @SuppressWarnings("unchecked")
    public Map<String, Object> listSessions(Long userId) {
        String targetUrl = pythonServiceUrl + "/api/chat/session/list?userId=" + userId;
        return webClient.get()
                .uri(targetUrl)
                .retrieve()
                .bodyToMono(Map.class)
                .timeout(Duration.ofSeconds(10))
                .block();
    }

    @Override
    @SuppressWarnings("unchecked")
    public Map<String, Object> getSessionMessages(String sessionId) {
        String targetUrl = pythonServiceUrl + "/api/chat/session/" + sessionId + "/messages";
        return webClient.get()
                .uri(targetUrl)
                .retrieve()
                .bodyToMono(Map.class)
                .timeout(Duration.ofSeconds(10))
                .block();
    }

    @Override
    @SuppressWarnings("unchecked")
    public Map<String, Object> deleteSession(String sessionId, Long userId) {
        String targetUrl = pythonServiceUrl + "/api/chat/session/" + sessionId + "?userId=" + userId;
        return webClient.delete()
                .uri(targetUrl)
                .retrieve()
                .bodyToMono(Map.class)
                .timeout(Duration.ofSeconds(10))
                .block();
    }
}
