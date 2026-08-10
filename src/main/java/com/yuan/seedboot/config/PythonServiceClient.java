package com.yuan.seedboot.config;

import cn.hutool.core.util.ObjUtil;
import cn.hutool.core.util.StrUtil;
import cn.hutool.http.HttpRequest;
import cn.hutool.http.HttpResponse;
import cn.hutool.json.JSONObject;
import cn.hutool.json.JSONUtil;
import com.yuan.seedboot.exception.BusinessException;
import com.yuan.seedboot.exception.ErrorCode;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.util.HashMap;
import java.util.Map;

/**
 * Python 微服务客户端：调用 Python /api/extract 接口执行 LLM 知识抽取
 */
@Slf4j
@Component
public class PythonServiceClient {

    @Value("${python.service.url:http://localhost:8001}")
    private String pythonServiceUrl;

    /**
     * 调用 Python 抽取接口
     *
     * @param text      待抽取文本
     * @param ontology  本体 JSON: {entities:[{name, properties}], relations:[{name, source, target, properties}]}
     * @param modelId   图谱模型 id
     * @param mode      抽取模式: zero_shot / few_shot / open
     * @return Python 响应 JSON: {entities:[], relations:[], tokenConsumed, duration}
     */
    public JSONObject extract(String text, Object ontology, Long modelId, String mode) {
        if (StrUtil.isBlank(text)) {
            throw new BusinessException(ErrorCode.PARAMS_ERROR, "待抽取文本为空");
        }
        Map<String, Object> payload = new HashMap<>();
        payload.put("text", text);
        payload.put("ontology", ontology);
        payload.put("modelId", modelId);
        payload.put("mode", mode);

        return doPost(pythonServiceUrl + "/api/extract", payload, modelId, "LLM");
    }

    /**
     * 调用 Python KOS 抽取接口
     *
     * @param text       待抽取文本
     * @param ontology   本体 JSON（可选，用于类型对齐）
     * @param modelId    图谱模型 id
     * @param kosConfig  KOS 抽取参数
     * @return Python 响应 JSON: {entities:[], relations:[], metrics:{}, tokenConsumed, duration, writeCount}
     */
    public JSONObject kosExtract(String text, Object ontology, Long modelId, Object kosConfig) {
        if (StrUtil.isBlank(text)) {
            throw new BusinessException(ErrorCode.PARAMS_ERROR, "待抽取文本为空");
        }
        Map<String, Object> payload = new HashMap<>();
        payload.put("text", text);
        payload.put("ontology", ontology);
        payload.put("modelId", modelId);
        payload.put("kosConfig", kosConfig);

        return doPost(pythonServiceUrl + "/api/kos/extract", payload, modelId, "KOS");
    }

    /**
     * 调用 Python 深度学习抽取接口
     *
     * @param text       待抽取文本
     * @param ontology   本体 JSON（可选，用于类型对齐）
     * @param modelId    图谱模型 id
     * @param dlConfig   深度学习抽取参数
     * @return Python 响应 JSON: {entities:[], relations:[], metrics:{}, tokenConsumed, duration, writeCount}
     */
    public JSONObject dlExtract(String text, Object ontology, Long modelId, Object dlConfig) {
        if (StrUtil.isBlank(text)) {
            throw new BusinessException(ErrorCode.PARAMS_ERROR, "待抽取文本为空");
        }
        Map<String, Object> payload = new HashMap<>();
        payload.put("text", text);
        payload.put("ontology", ontology);
        payload.put("modelId", modelId);
        payload.put("dlConfig", dlConfig);

        return doPost(pythonServiceUrl + "/api/dl/extract", payload, modelId, "DL");
    }

    /**
     * 调用 Python 训练接口
     *
     * @param annotationData 标注数据: {entities:[], relations:[], text}
     * @param trainConfig    训练配置: {dataset, architecture, epochs, version}
     * @param modelId        模型 id（可选）
     * @return Python 响应 JSON: {history:{}, metrics:{}, duration}
     */
    public JSONObject train(Object annotationData, Object trainConfig, Long modelId) {
        if (ObjUtil.isNull(annotationData)) {
            throw new BusinessException(ErrorCode.PARAMS_ERROR, "标注数据为空");
        }
        Map<String, Object> payload = new HashMap<>();
        payload.put("annotationData", annotationData);
        payload.put("trainConfig", trainConfig);
        payload.put("modelId", modelId);

        return doPost(pythonServiceUrl + "/api/train", payload, modelId, "TRAIN");
    }

    /**
     * 通用 POST 请求封装
     */
    private JSONObject doPost(String url, Map<String, Object> payload, Long modelId, String type) {
        String body = JSONUtil.toJsonStr(payload);
        log.info("调用 Python {} 抽取服务, url={}, modelId={}, textLength={}", type, url, modelId,
                payload.get("text") == null ? 0 : String.valueOf(payload.get("text")).length());

        try (HttpResponse response = HttpRequest.post(url)
                .header("Content-Type", "application/json")
                .body(body)
                .timeout(600_000)
                .execute()) {
            String respBody = response.body();
            if (!response.isOk()) {
                log.error("Python {} 抽取服务返回失败, status={}, body={}", type, response.getStatus(), respBody);
                throw new BusinessException(ErrorCode.OPERATION_ERROR,
                        "Python " + type + " 抽取服务返回失败: " + response.getStatus());
            }
            log.info("Python {} 抽取服务调用成功, modelId={}", type, modelId);
            return JSONUtil.parseObj(respBody);
        } catch (BusinessException e) {
            throw e;
        } catch (Exception e) {
            log.error("调用 Python {} 抽取服务异常, url={}", type, url, e);
            throw new BusinessException(ErrorCode.OPERATION_ERROR,
                    "调用 Python " + type + " 抽取服务异常: " + e.getMessage());
        }
    }
}
