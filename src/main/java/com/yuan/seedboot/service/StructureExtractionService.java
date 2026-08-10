package com.yuan.seedboot.service;

import com.yuan.seedboot.model.entity.ExtractionTask;
import com.yuan.seedboot.model.entity.User;
import com.yuan.seedboot.model.request.StructureExtractionRequest;

import java.util.List;
import java.util.Map;

/**
 * （半）结构化数据抽取服务
 * 负责 CSV/Excel 文件解析、字段映射、Neo4j 批量写入
 */
public interface StructureExtractionService {

    /**
     * 解析上传文件，返回列名和预览数据
     *
     * @param fileBytes 文件字节数组
     * @param fileName  文件名（用于判断格式）
     * @return {fileKey, columns, previewRows, totalRows}
     */
    Map<String, Object> parseFile(byte[] fileBytes, String fileName);

    /**
     * 执行结构化抽取：按映射配置将数据写入 Neo4j，并记录抽取任务
     *
     * @param request   映射配置
     * @param loginUser 当前登录用户
     * @return 抽取任务记录
     */
    ExtractionTask executeExtraction(StructureExtractionRequest request, User loginUser);
}
