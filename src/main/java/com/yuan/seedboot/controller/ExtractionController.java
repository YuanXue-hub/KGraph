package com.yuan.seedboot.controller;

import cn.hutool.json.JSONObject;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.yuan.seedboot.common.BaseResponse;
import com.yuan.seedboot.common.PageRequest;
import com.yuan.seedboot.common.ResultUtils;
import com.yuan.seedboot.config.PythonServiceClient;
import com.yuan.seedboot.exception.ErrorCode;
import com.yuan.seedboot.exception.ThrowUtils;
import com.yuan.seedboot.model.entity.EvaluationRecord;
import com.yuan.seedboot.model.entity.ExtractionTask;
import com.yuan.seedboot.model.entity.User;
import com.yuan.seedboot.model.request.ExtractionDlRequest;
import com.yuan.seedboot.model.request.ExtractionKosRequest;
import com.yuan.seedboot.model.request.ExtractionRequest;
import com.yuan.seedboot.model.request.StructureExtractionRequest;
import com.yuan.seedboot.service.EvaluationRecordService;
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

    @Resource
    private PythonServiceClient pythonServiceClient;

    @Resource
    private EvaluationRecordService evaluationRecordService;

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

    @PostMapping("/evaluate")
    @Operation(summary = "LLM 抽取质量评估（内在指标 + G-Eval 风格 LLM-as-Judge，调 Python），结果存入评估历史")
    public BaseResponse<Map<String, Object>> evaluate(@RequestBody Map<String, Object> request, HttpServletRequest httpRequest) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        User loginUser = userService.getLoginUser(httpRequest);
        JSONObject result = pythonServiceClient.evaluate(request);
        // hutool 会把 JSON null 解析为 JSONNull 对象，Jackson 无法序列化；
        // 这里用 Jackson 重新解析原始 JSON 字符串，null 还原为 Java null
        Map<String, Object> plain;
        try {
            plain = new com.fasterxml.jackson.databind.ObjectMapper()
                    .readValue(result.toString(), Map.class);
        } catch (Exception e) {
            throw new com.yuan.seedboot.exception.BusinessException(ErrorCode.OPERATION_ERROR,
                    "评估结果解析失败: " + e.getMessage());
        }
        // 持久化评估历史（taskId 由前端传入；保存失败不阻断评估结果返回）
        try {
            EvaluationRecord record = new EvaluationRecord();
            Object taskIdObj = request.get("taskId");
            record.setTaskId(taskIdObj != null ? Long.parseLong(String.valueOf(taskIdObj)) : 0L);
            Object sampleObj = request.get("sampleSize");
            record.setSampleSize(sampleObj != null ? Integer.parseInt(String.valueOf(sampleObj)) : 30);
            Object overallObj = plain.get("overall");
            record.setOverall(overallObj != null ? Double.parseDouble(String.valueOf(overallObj)) : null);
            record.setResult(result.toString());
            Object tokenObj = plain.get("tokenConsumed");
            record.setTokenConsumed(tokenObj != null ? Integer.parseInt(String.valueOf(tokenObj)) : null);
            Object durObj = plain.get("duration");
            record.setDuration(durObj != null ? Long.parseLong(String.valueOf(durObj)) : null);
            record.setCreateBy(loginUser != null ? loginUser.getId() : null);
            evaluationRecordService.save(record);
            plain.put("evaluationId", record.getId());
        } catch (Exception ignore) {
            // 历史保存失败不影响评估本身
        }
        return ResultUtils.success(plain);
    }

    @GetMapping("/evaluate/list")
    @Operation(summary = "分页查询评估历史列表（taskId 可选：传则查该任务，不传查全部；时间倒序）")
    public BaseResponse<Page<EvaluationRecord>> listEvaluations(Long taskId, PageRequest pageRequest) {
        return ResultUtils.success(evaluationRecordService.listByTaskId(taskId, pageRequest));
    }

    @PostMapping("/evaluate/delete")
    @Operation(summary = "删除评估历史记录（逻辑删除）")
    public BaseResponse<Boolean> deleteEvaluation(@RequestBody Map<String, Object> request) {
        ThrowUtils.throwIf(request == null || request.get("id") == null, ErrorCode.PARAMS_ERROR, "id 非法");
        long id = Long.parseLong(String.valueOf(request.get("id")));
        ThrowUtils.throwIf(id <= 0, ErrorCode.PARAMS_ERROR, "id 非法");
        boolean removed = evaluationRecordService.removeById(id);
        ThrowUtils.throwIf(!removed, ErrorCode.NOT_FOUND_ERROR, "评估记录不存在");
        return ResultUtils.success(true);
    }

    @GetMapping("/evaluate/get")
    @Operation(summary = "获取评估历史详情（含完整报告 JSON）")
    public BaseResponse<Map<String, Object>> getEvaluation(long id) {
        ThrowUtils.throwIf(id <= 0, ErrorCode.PARAMS_ERROR);
        EvaluationRecord record = evaluationRecordService.getById(id);
        ThrowUtils.throwIf(record == null, ErrorCode.NOT_FOUND_ERROR, "评估记录不存在");
        try {
            Map<String, Object> plain = new com.fasterxml.jackson.databind.ObjectMapper()
                    .readValue(record.getResult(), Map.class);
            plain.put("evaluationId", record.getId());
            plain.put("taskId", record.getTaskId());
            plain.put("sampleSize", record.getSampleSize());
            plain.put("evalCreateTime", record.getCreateTime() != null ? record.getCreateTime().getTime() : null);
            return ResultUtils.success(plain);
        } catch (Exception e) {
            throw new com.yuan.seedboot.exception.BusinessException(ErrorCode.OPERATION_ERROR,
                    "评估记录解析失败: " + e.getMessage());
        }
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

    @PostMapping("/delete")
    @Operation(summary = "删除抽取任务记录（逻辑删除）")
    public BaseResponse<Boolean> deleteExtractionTask(@RequestBody Map<String, Object> request) {
        ThrowUtils.throwIf(request == null || request.get("id") == null, ErrorCode.PARAMS_ERROR, "id 非法");
        long id = Long.parseLong(String.valueOf(request.get("id")));
        ThrowUtils.throwIf(id <= 0, ErrorCode.PARAMS_ERROR, "id 非法");
        boolean removed = extractionTaskService.removeById(id);
        ThrowUtils.throwIf(!removed, ErrorCode.NOT_FOUND_ERROR, "抽取任务不存在");
        return ResultUtils.success(true);
    }
}
