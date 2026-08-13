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
    public Flux<ServerSentEvent<String>> chatAgentStream(String message, Long modelId) {
        Map<String, Object> payload = Map.of(
                "message", message,
                "modelId", modelId != null ? modelId : 0
        );

        String targetUrl = pythonServiceUrl + "/api/chat/agent/stream";
        log.info("Chat Agent SSE proxy: url={}, modelId={}", targetUrl, modelId);

        ParameterizedTypeReference<ServerSentEvent<String>> sseType =
                new ParameterizedTypeReference<>() {};

        return webClient.post()
                .uri(targetUrl)
                .contentType(MediaType.APPLICATION_JSON)
                .accept(MediaType.TEXT_EVENT_STREAM)
                .bodyValue(payload)
                .retrieve()
                .bodyToFlux(sseType)
                // 兜底超时（单条事件超过30秒视为上游异常）
                .timeout(Duration.ofSeconds(60))
                .doOnNext(sse -> log.debug("SSE proxy emit event: data={}",
                        sse.data() != null
                                ? sse.data().substring(0, Math.min(80, sse.data().length()))
                                : "<null>"))
                .doOnError(e -> log.error("Chat Agent SSE proxy error", e))
                .doOnComplete(() -> log.info("Chat Agent SSE proxy stream completed"));
    }
}
