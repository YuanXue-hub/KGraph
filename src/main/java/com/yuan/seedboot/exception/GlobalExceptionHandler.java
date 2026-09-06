package com.yuan.seedboot.exception;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.yuan.seedboot.common.BaseResponse;
import com.yuan.seedboot.common.ResultUtils;
import io.swagger.v3.oas.annotations.Hidden;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.reactive.function.client.WebClientResponseException;

@Hidden
@RestControllerAdvice
@Slf4j
public class GlobalExceptionHandler {

    private static final ObjectMapper OBJECT_MAPPER = new ObjectMapper();

    @ExceptionHandler(BusinessException.class)
    public BaseResponse<?> businessExceptionHandler(BusinessException e) {
        log.error("BusinessException", e);
        return ResultUtils.error(e.getCode(), e.getMessage());
    }

    /**
     * Python 服务错误透传：解析 FastAPI HTTPException 响应体（{detail: "..."}），
     * 保留原始校验信息（如「DeepSeek 需要填写 API Key」），避免一律显示「系统错误」。
     */
    @ExceptionHandler(WebClientResponseException.class)
    public BaseResponse<?> webClientResponseExceptionHandler(WebClientResponseException e) {
        String detail = null;
        try {
            String body = e.getResponseBodyAsString();
            if (body != null && !body.isBlank()) {
                JsonNode node = OBJECT_MAPPER.readTree(body);
                if (node.hasNonNull("detail")) {
                    detail = node.get("detail").asText();
                } else if (node.hasNonNull("message")) {
                    detail = node.get("message").asText();
                }
            }
        } catch (Exception ignored) {
        }
        log.warn("Python service error: {} -> {}", e.getStatusCode(), detail != null ? detail : e.getMessage());
        return ResultUtils.error(ErrorCode.SYSTEM_ERROR, detail != null ? detail : "后端服务请求失败");
    }

    @ExceptionHandler(RuntimeException.class)
    public BaseResponse<?> runtimeExceptionHandler(RuntimeException e) {
        log.error("RuntimeException", e);
        return ResultUtils.error(ErrorCode.SYSTEM_ERROR, "系统错误");
    }
}
