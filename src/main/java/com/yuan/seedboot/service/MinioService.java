package com.yuan.seedboot.service;

import com.yuan.seedboot.config.MinioConfig;
import com.yuan.seedboot.exception.BusinessException;
import com.yuan.seedboot.exception.ErrorCode;
import io.minio.BucketExistsArgs;
import io.minio.MakeBucketArgs;
import io.minio.MinioClient;
import io.minio.PutObjectArgs;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.InputStream;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.UUID;

/**
 * MinIO 对象存储服务
 */
@Slf4j
@Service
public class MinioService {

    @Resource
    private MinioClient minioClient;

    @Resource
    private MinioConfig minioConfig;

    /**
     * 上传文件到默认桶，返回可访问的对象 URL
     *
     * @param file 上传的文件
     * @param dir  桶内目录（如 avatar、corpus），为空时放在根目录
     * @return 文件访问 URL
     */
    public String uploadFile(MultipartFile file, String dir) {
        if (file == null || file.isEmpty()) {
            throw new BusinessException(ErrorCode.PARAMS_ERROR, "文件为空");
        }
        String bucket = minioConfig.getBucket();
        try {
            // 确保桶存在
            ensureBucket(bucket);
            // 生成对象名：dir/yyyyMMdd/uuid.扩展名
            String originalFilename = file.getOriginalFilename();
            String suffix = "";
            if (originalFilename != null && originalFilename.contains(".")) {
                suffix = originalFilename.substring(originalFilename.lastIndexOf("."));
            }
            String datePath = LocalDate.now().format(DateTimeFormatter.ofPattern("yyyyMMdd"));
            String objectName = (dir == null ? "" : dir + "/") + datePath + "/"
                    + UUID.randomUUID().toString().replace("-", "") + suffix;
            // 上传
            try (InputStream inputStream = file.getInputStream()) {
                minioClient.putObject(
                        PutObjectArgs.builder()
                                .bucket(bucket)
                                .object(objectName)
                                .stream(inputStream, file.getSize(), -1)
                                .contentType(file.getContentType())
                                .build()
                );
            }
            // 拼接访问 URL（桶设为 public-read 时可直接访问）
            String url = minioConfig.getEndpoint() + "/" + bucket + "/" + objectName;
            log.info("MinIO 文件上传成功: {}", url);
            return url;
        } catch (Exception e) {
            log.error("MinIO 文件上传失败", e);
            throw new BusinessException(ErrorCode.SYSTEM_ERROR, "文件上传失败: " + e.getMessage());
        }
    }

    /**
     * 上传文件到默认桶的根目录
     */
    public String uploadFile(MultipartFile file) {
        return uploadFile(file, null);
    }

    /**
     * 确保桶存在，不存在则创建
     */
    public void ensureBucket(String bucket) throws Exception {
        boolean exists = minioClient.bucketExists(
                BucketExistsArgs.builder().bucket(bucket).build()
        );
        if (!exists) {
            minioClient.makeBucket(MakeBucketArgs.builder().bucket(bucket).build());
            log.info("MinIO 桶已自动创建: {}", bucket);
        }
    }
}
