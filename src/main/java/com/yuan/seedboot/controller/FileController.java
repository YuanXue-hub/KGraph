package com.yuan.seedboot.controller;

import com.yuan.seedboot.common.BaseResponse;
import com.yuan.seedboot.common.ResultUtils;
import com.yuan.seedboot.service.MinioService;
import io.swagger.v3.oas.annotations.Operation;
import jakarta.annotation.Resource;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

/**
 * 文件上传接口（基于 MinIO 对象存储）
 */
@RestController
@RequestMapping("/file")
public class FileController {

    @Resource
    private MinioService minioService;

    /**
     * 通用文件上传
     *
     * @param file 文件
     * @param dir  桶内目录（可选）
     */
    @PostMapping("/upload")
    @Operation(summary = "文件上传", description = "上传文件到 MinIO，返回可访问 URL")
    public BaseResponse<String> upload(@RequestParam("file") MultipartFile file,
                                       @RequestParam(value = "dir", required = false) String dir) {
        String url = minioService.uploadFile(file, dir);
        return ResultUtils.success(url);
    }

    /**
     * 头像上传（固定目录 avatar）
     */
    @PostMapping("/upload/avatar")
    @Operation(summary = "头像上传", description = "上传头像到 MinIO 的 avatar 目录")
    public BaseResponse<String> uploadAvatar(@RequestParam("file") MultipartFile file) {
        String url = minioService.uploadFile(file, "avatar");
        return ResultUtils.success(url);
    }
}
