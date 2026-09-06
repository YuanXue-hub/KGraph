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
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

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
     * @param text       待抽取文本
     * @param ontology   本体 JSON: {entities:[{name, properties}], relations:[{name, source, target, properties}]}
     * @param modelId    图谱模型 id
     * @param mode       抽取模式: zero_shot / few_shot / open
     * @param llmModelId 抽取 LLM 模型 id（可选，空则用 Python 服务默认配置）
     * @return Python 响应 JSON: {entities:[], relations:[], tokenConsumed, duration}
     */
    public JSONObject extract(String text, Object ontology, Long modelId, String mode, Long llmModelId, Long userId) {
        if (StrUtil.isBlank(text)) {
            throw new BusinessException(ErrorCode.PARAMS_ERROR, "待抽取文本为空");
        }
        Map<String, Object> payload = new HashMap<>();
        payload.put("text", text);
        payload.put("ontology", ontology);
        payload.put("modelId", modelId);
        payload.put("mode", mode);
        if (ObjUtil.isNotNull(llmModelId)) {
            payload.put("llmModelId", llmModelId);
        }
        if (ObjUtil.isNotNull(userId)) {
            payload.put("userId", userId);
        }

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
     * 调用 Python 抽取质量评估接口（G-Eval 风格 LLM-as-Judge + 内在指标）
     *
     * @param payload 评估请求: {text, entities:[], relations:[], sampleSize}
     * @return Python 响应 JSON: {intrinsic:{}, llmJudge:{}, overall, duration, tokenConsumed}
     */
    public JSONObject evaluate(Map<String, Object> payload) {
        if (StrUtil.isBlank(String.valueOf(payload.get("text")))) {
            throw new BusinessException(ErrorCode.PARAMS_ERROR, "待评估原文为空");
        }
        return doPost(pythonServiceUrl + "/api/evaluate", payload, null, "EVAL");
    }

    /**
     * 调用 Python 流式评估接口（SSE），逐事件转发给 SseEmitter（不调用 complete，由调用方收尾），
     * 同时聚合完整评估报告（结构同 /api/evaluate 返回）供持久化
     *
     * @param payload 评估请求（同 evaluate）
     * @param emitter Spring SSE 发射器，事件原样转发给前端
     * @return 完整评估报告 JSON 字符串（含 intrinsic/llmJudge/overall 等；无 done 事件时为 null）
     */
    public String evaluateStreamForward(Map<String, Object> payload, SseEmitter emitter) {
        String url = pythonServiceUrl + "/api/evaluate/stream";
        String body = JSONUtil.toJsonStr(payload);
        log.info("调用 Python 流式评估服务, url={}, textLength={}",
                url, payload.get("text") == null ? 0 : String.valueOf(payload.get("text")).length());

        try (HttpResponse response = HttpRequest.post(url)
                .header("Content-Type", "application/json")
                .header("Accept", "text/event-stream")
                .body(body)
                .timeout(600_000)
                .executeAsync()) {
            if (!response.isOk()) {
                throw new BusinessException(ErrorCode.OPERATION_ERROR,
                        "Python 评估服务返回失败: " + response.getStatus());
            }
            // 聚合完整报告：{intrinsic:{}, llmJudge:{key:{...}}, overall, ...}
            cn.hutool.json.JSONConfig cfg = cn.hutool.json.JSONConfig.create().setIgnoreNullValue(false);
            JSONObject report = new JSONObject(cfg);
            JSONObject judgeAgg = new JSONObject(cfg);
            boolean hasDone = false;
            try (java.io.BufferedReader reader = new java.io.BufferedReader(
                    new java.io.InputStreamReader(response.bodyStream(), java.nio.charset.StandardCharsets.UTF_8))) {
                String line;
                String eventName = "message";
                StringBuilder dataBuf = new StringBuilder();
                while ((line = reader.readLine()) != null) {
                    if (line.isEmpty()) {
                        if (dataBuf.length() > 0) {
                            String data = dataBuf.toString();
                            switch (eventName) {
                                case "intrinsic" -> report.set("intrinsic", JSONUtil.parseObj(data));
                                case "metric" -> {
                                    JSONObject m = JSONUtil.parseObj(data);
                                    judgeAgg.set(m.getStr("key"), m.get("data"));
                                }
                                case "done" -> {
                                    hasDone = true;
                                    JSONObject d = JSONUtil.parseObj(data);
                                    for (String k : d.keySet()) {
                                        report.set(k, d.get(k));
                                    }
                                }
                                default -> { /* error 等事件只转发不聚合 */ }
                            }
                            emitter.send(SseEmitter.event().name(eventName).data(data));
                            dataBuf.setLength(0);
                            eventName = "message";
                        }
                    } else if (line.startsWith("event:")) {
                        eventName = line.substring(6).trim();
                    } else if (line.startsWith("data:")) {
                        dataBuf.append(line.substring(5).trim());
                    }
                }
            }
            if (!hasDone) {
                return null;
            }
            report.set("llmJudge", judgeAgg);
            return report.toString();
        } catch (BusinessException e) {
            throw e;
        } catch (Exception e) {
            log.error("调用 Python 流式评估服务异常, url={}", url, e);
            throw new BusinessException(ErrorCode.OPERATION_ERROR,
                    "调用 Python 流式评估服务异常: " + e.getMessage());
        }
    }

    /**
     * 调用 Python 分块接口（无状态纯函数）
     *
     * @param text        待分块文本
     * @param strategy    分块策略: fixed/sentence/recursive/structure
     * @param chunkSize   块大小（字符，可空取策略默认）
     * @param overlap     重叠（字符，可空取策略默认）
     * @param separator   自定义一级分隔符（仅 recursive，可空）
     * @param previewOnly true 时仅返回前 10 块（totalChunks 仍为真实总数）
     * @return Python 响应 JSON: {strategy, chunkSize, overlap, totalChunks, avgCharCount, duration, chunks:[{index, content, startOffset, endOffset, charCount}]}
     */
    public JSONObject splitText(String text, String strategy, Integer chunkSize, Integer overlap,
                                String separator, boolean previewOnly) {
        if (StrUtil.isBlank(text)) {
            throw new BusinessException(ErrorCode.PARAMS_ERROR, "待分块文本为空");
        }
        Map<String, Object> payload = new HashMap<>();
        payload.put("text", text);
        payload.put("strategy", strategy);
        if (ObjUtil.isNotNull(chunkSize)) {
            payload.put("chunkSize", chunkSize);
        }
        if (ObjUtil.isNotNull(overlap)) {
            payload.put("overlap", overlap);
        }
        if (StrUtil.isNotBlank(separator)) {
            payload.put("separator", separator);
        }
        if (previewOnly) {
            payload.put("previewOnly", true);
        }
        return doPost(pythonServiceUrl + "/api/split", payload, null, "SPLIT");
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
                // 附带 Python 错误详情（截断防超长），便于前端展示具体原因（如分块数超限）
                String detail = StrUtil.blankToDefault(StrUtil.sub(respBody, 0, 200), "");
                throw new BusinessException(ErrorCode.OPERATION_ERROR,
                        "Python " + type + " 服务返回失败: " + response.getStatus() + " " + detail);
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
