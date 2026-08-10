package com.yuan.seedboot.controller;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.yuan.seedboot.common.BaseResponse;
import com.yuan.seedboot.common.PageRequest;
import com.yuan.seedboot.common.ResultUtils;
import com.yuan.seedboot.exception.ErrorCode;
import com.yuan.seedboot.exception.ThrowUtils;
import com.yuan.seedboot.model.entity.ExtractionTask;
import com.yuan.seedboot.model.entity.User;
import com.yuan.seedboot.model.request.ExtractionDlRequest;
import com.yuan.seedboot.model.request.ExtractionKosRequest;
import com.yuan.seedboot.model.request.ExtractionRequest;
import com.yuan.seedboot.model.request.StructureExtractionRequest;
import com.yuan.seedboot.service.ExtractionTaskService;
import com.yuan.seedboot.service.StructureExtractionService;
import com.yuan.seedboot.service.UserService;
import io.swagger.v3.oas.annotations.Operation;
import jakarta.annotation.Resource;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.Map;

/**
 * 知识抽取 Controller
 */
@RestController
@RequestMapping("/extraction")
public class ExtractionController {

    @Resource
    private ExtractionTaskService extractionTaskService;

    @Resource
    private UserService userService;

    @Resource
    private StructureExtractionService structureExtractionService;

    @PostMapping("/llm")
    @Operation(summary = "LLM 知识抽取（调 Python，Python 抽取后直接写入 Neo4j）")
    public BaseResponse<ExtractionTask> llmExtract(@RequestBody ExtractionRequest request, HttpServletRequest httpRequest) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        User loginUser = userService.getLoginUser(httpRequest);
        ExtractionTask task = extractionTaskService.createExtraction(request, loginUser);
        return ResultUtils.success(task);
    }

    @PostMapping("/kos")
    @Operation(summary = "KOS 知识抽取（基于知识组织体系，词表驱动 + TF-IDF，不依赖 LLM）")
    public BaseResponse<ExtractionTask> kosExtract(@RequestBody ExtractionKosRequest request, HttpServletRequest httpRequest) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        User loginUser = userService.getLoginUser(httpRequest);
        ExtractionTask task = extractionTaskService.createKosExtraction(request, loginUser);
        return ResultUtils.success(task);
    }

    @PostMapping("/dl")
    @Operation(summary = "深度学习知识抽取（BiLSTM-CRF 命名实体识别 + 神经网络关系抽取，不依赖 LLM）")
    public BaseResponse<ExtractionTask> dlExtract(@RequestBody ExtractionDlRequest request, HttpServletRequest httpRequest) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        User loginUser = userService.getLoginUser(httpRequest);
        ExtractionTask task = extractionTaskService.createDlExtraction(request, loginUser);
        return ResultUtils.success(task);
    }

    @PostMapping("/structure/parse")
    @Operation(summary = "上传并解析结构化文件（CSV/Excel），返回列名与预览数据")
    public BaseResponse<Map<String, Object>> parseStructureFile(@RequestParam("file") MultipartFile file) {
        ThrowUtils.throwIf(file == null || file.isEmpty(), ErrorCode.PARAMS_ERROR, "文件为空");
        try {
            Map<String, Object> result = structureExtractionService.parseFile(file.getBytes(), file.getOriginalFilename());
            return ResultUtils.success(result);
        } catch (java.io.IOException e) {
            throw new com.yuan.seedboot.exception.BusinessException(ErrorCode.OPERATION_ERROR, "文件读取失败: " + e.getMessage());
        }
    }

    @PostMapping("/structure")
    @Operation(summary = "（半）结构化数据抽取（按字段映射写入 Neo4j，不经过 Python）")
    public BaseResponse<ExtractionTask> structureExtract(@RequestBody StructureExtractionRequest request, HttpServletRequest httpRequest) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        User loginUser = userService.getLoginUser(httpRequest);
        ExtractionTask task = structureExtractionService.executeExtraction(request, loginUser);
        return ResultUtils.success(task);
    }

    @GetMapping("/list")
    @Operation(summary = "抽取任务列表")
    public BaseResponse<Page<ExtractionTask>> listExtractionTasks(Long projectId, String extractionType, PageRequest pageRequest) {
        ThrowUtils.throwIf(pageRequest == null, ErrorCode.PARAMS_ERROR);
        Page<ExtractionTask> page = extractionTaskService.listExtractionTasks(projectId, extractionType, pageRequest);
        return ResultUtils.success(page);
    }

    @GetMapping("/get")
    @Operation(summary = "抽取任务详情")
    public BaseResponse<ExtractionTask> getExtractionTask(long id) {
        ThrowUtils.throwIf(id <= 0, ErrorCode.PARAMS_ERROR);
        ExtractionTask task = extractionTaskService.getExtractionTask(id);
        return ResultUtils.success(task);
    }
}
