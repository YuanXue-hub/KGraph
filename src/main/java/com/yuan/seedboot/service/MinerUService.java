package com.yuan.seedboot.service;

import cn.hutool.core.util.StrUtil;
import cn.hutool.json.JSONArray;
import cn.hutool.json.JSONObject;
import cn.hutool.json.JSONUtil;
import com.yuan.seedboot.config.MinioConfig;
import com.yuan.seedboot.mapper.CorpusMapper;
import com.yuan.seedboot.model.entity.Corpus;
import com.baomidou.mybatisplus.core.conditions.update.UpdateWrapper;
import io.minio.GetObjectArgs;
import io.minio.MinioClient;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.MediaType;
import org.springframework.http.client.MultipartBodyBuilder;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.BodyInserters;
import org.springframework.web.reactive.function.client.WebClient;

import java.io.InputStream;
import java.time.Duration;

/**
 * MinerU 文档解析服务
 * 封装与 MinerU API（mineru-api --port 8000）的交互逻辑
 */
@Slf4j
@Service
public class MinerUService {

    @Value("${mineru.base-url}")
    private String baseUrl;

    private final WebClient webClient;
    private final CorpusMapper corpusMapper;
    private final MinioClient minioClient;
    private final MinioConfig minioConfig;

    public MinerUService(WebClient.Builder webClientBuilder, CorpusMapper corpusMapper,
                         MinioClient minioClient, MinioConfig minioConfig) {
        this.webClient = webClientBuilder
                .codecs(configurer -> configurer.defaultCodecs().maxInMemorySize(50 * 1024 * 1024))
                .build();
        this.corpusMapper = corpusMapper;
        this.minioClient = minioClient;
        this.minioConfig = minioConfig;
    }

    /**
     * 同步调用 MinerU /file_parse 解析文件，返回 Markdown 文本
     *
     * @param fileUrl  文件的 MinIO URL
     * @param fileName 文件名（含扩展名，用于 MinerU 识别文件类型）
     * @return 解析后的 Markdown 文本
     */
    public String parseFileFromUrl(String fileUrl, String fileName) {
        // 1. 从 MinIO 下载文件（使用 MinIO SDK，避免 403）
        byte[] fileBytes = downloadFromMinio(fileUrl);

        // 2. 构建 multipart 请求
        String finalFileName = StrUtil.isNotBlank(fileName) ? fileName : extractFileName(fileUrl);
        MultipartBodyBuilder builder = new MultipartBodyBuilder();
        builder.part("files", new ByteArrayResource(fileBytes) {
            @Override
            public String getFilename() {
                return finalFileName;
            }
        });
        builder.part("return_md", "true");

        // 3. 调用 MinerU /file_parse（同步接口，设置 10 分钟超时）
        String response = webClient.post()
                .uri(baseUrl + "/file_parse")
                .contentType(MediaType.MULTIPART_FORM_DATA)
                .body(BodyInserters.fromMultipartData(builder.build()))
                .retrieve()
                .bodyToMono(String.class)
                .block(Duration.ofMinutes(10));

        return extractMarkdown(response);
    }

    /**
     * 使用 MinIO SDK 下载文件
     * fileUrl 格式: http://localhost:9000/kgraph/corpus/20260815/xxx.pdf
     */
    private byte[] downloadFromMinio(String fileUrl) {
        String bucket = minioConfig.getBucket();
        String endpoint = minioConfig.getEndpoint();
        // 从 URL 中提取 objectName: 去掉 endpoint + "/" + bucket + "/"
        String prefix = endpoint + "/" + bucket + "/";
        String objectName;
        if (fileUrl.startsWith(prefix)) {
            objectName = fileUrl.substring(prefix.length());
        } else {
            // 兜底：取 URL 路径中 bucket 之后的部分
            int bucketIdx = fileUrl.indexOf("/" + bucket + "/");
            if (bucketIdx >= 0) {
                objectName = fileUrl.substring(bucketIdx + bucket.length() + 2);
            } else {
                throw new RuntimeException("无法从 URL 解析 objectName: " + fileUrl);
            }
        }

        log.info("从 MinIO 下载文件: bucket={}, object={}", bucket, objectName);
        try (InputStream stream = minioClient.getObject(
                GetObjectArgs.builder()
                        .bucket(bucket)
                        .object(objectName)
                        .build()
        )) {
            return stream.readAllBytes();
        } catch (Exception e) {
            throw new RuntimeException("从 MinIO 下载文件失败: " + fileUrl, e);
        }
    }

    /**
     * 异步解析语料文件，解析完成后自动更新 corpus 记录的状态和内容
     *
     * @param corpusId 语料 ID
     * @param fileUrl  文件的 MinIO URL
     * @param fileName 原始文件名
     */
    @Async
    public void parseCorpusAsync(Long corpusId, String fileUrl, String fileName) {
        log.info("开始异步解析语料: corpusId={}, file={}", corpusId, fileName);
        try {
            String markdown = parseFileFromUrl(fileUrl, fileName);
            // 使用 UpdateWrapper 确保 errorMsg 被清除为 null
            UpdateWrapper<Corpus> wrapper = new UpdateWrapper<>();
            wrapper.eq("id", corpusId)
                    .set("content", markdown)
                    .set("status", 1)
                    .set("errorMsg", null);
            corpusMapper.update(null, wrapper);
            log.info("语料 {} MinerU 解析完成，内容长度: {}", corpusId, markdown.length());
        } catch (Exception e) {
            log.error("语料 {} MinerU 解析失败", corpusId, e);
            Corpus update = new Corpus();
            update.setId(corpusId);
            update.setStatus(2); // 失败
            update.setErrorMsg(StrUtil.sub(e.getMessage(), 0, 500));
            corpusMapper.updateById(update);
        }
    }

    /**
     * 从 MinerU 响应中提取 Markdown 文本
     * MinerU v3.4.5 /file_parse 响应格式:
     * {"task_id":"...","status":"completed","results":{"<filename>":{"md_content":"..."}}}
     * 也兼容旧格式: [{"md":"..."}] 或 {"md":"..."} 或纯文本
     */
    private String extractMarkdown(String response) {
        if (StrUtil.isBlank(response)) {
            throw new RuntimeException("MinerU 返回空响应");
        }
        try {
            JSONObject obj = JSONUtil.parseObj(response);
            // MinerU v3.4.5: results.<filename>.md_content
            if (obj.containsKey("results")) {
                JSONObject results = obj.getJSONObject("results");
                if (results != null) {
                    for (String key : results.keySet()) {
                        JSONObject item = results.getJSONObject(key);
                        if (item != null) {
                            // 优先 md_content
                            if (item.containsKey("md_content")) {
                                return item.getStr("md_content");
                            }
                            if (item.containsKey("md")) {
                                return item.getStr("md");
                            }
                        }
                    }
                }
            }
            // 兼容: 直接有 md 字段
            if (obj.containsKey("md")) {
                return obj.getStr("md");
            }
            // 兼容: results 是数组
            if (obj.containsKey("results")) {
                JSONArray arr = obj.getJSONArray("results");
                if (arr != null && !arr.isEmpty()) {
                    JSONObject first = arr.getJSONObject(0);
                    if (first != null && first.containsKey("md")) {
                        return first.getStr("md");
                    }
                }
            }
        } catch (Exception ignored) {
        }
        // 兼容: JSON 数组
        try {
            JSONArray arr = JSONUtil.parseArray(response);
            if (!arr.isEmpty()) {
                JSONObject first = arr.getJSONObject(0);
                if (first != null && first.containsKey("md")) {
                    return first.getStr("md");
                }
            }
        } catch (Exception ignored) {
        }
        // 如果是 JSON 但没找到 md 字段，返回原始文本（方便调试）
        return response;
    }

    private String extractFileName(String url) {
        return url.substring(url.lastIndexOf('/') + 1);
    }
}
