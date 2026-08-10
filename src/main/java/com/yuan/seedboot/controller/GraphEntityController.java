package com.yuan.seedboot.controller;

import cn.hutool.core.util.StrUtil;
import com.yuan.seedboot.common.BaseResponse;
import com.yuan.seedboot.common.ResultUtils;
import com.yuan.seedboot.exception.ErrorCode;
import com.yuan.seedboot.exception.ThrowUtils;
import com.yuan.seedboot.model.request.EntityNeo4jAddRequest;
import com.yuan.seedboot.model.request.EntityNeo4jNodeIdRequest;
import com.yuan.seedboot.model.request.EntityNeo4jUpdateRequest;
import com.yuan.seedboot.model.request.EntityPropertyDeleteRequest;
import com.yuan.seedboot.model.request.EntityPropertySetRequest;
import com.yuan.seedboot.service.Neo4jService;
import io.swagger.v3.oas.annotations.Operation;
import jakarta.annotation.Resource;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * Neo4j 实体管理 Controller
 * <p>
 * 提供图谱模型下实体（节点）和属性的增删改查，直接操作 Neo4j 数据层。
 */
@RestController
@RequestMapping("/entity")
public class GraphEntityController {

    @Resource
    private Neo4jService neo4jService;

    @GetMapping("/list")
    @Operation(summary = "实体列表（按 modelId 分页）")
    public BaseResponse<Map<String, Object>> listEntities(
            long modelId,
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "20") int pageSize) {
        ThrowUtils.throwIf(modelId <= 0, ErrorCode.PARAMS_ERROR);
        ThrowUtils.throwIf(pageNum <= 0 || pageSize <= 0 || pageSize > 500, ErrorCode.PARAMS_ERROR, "分页参数有误");
        Map<String, Object> data = neo4jService.listEntities(modelId, keyword, pageNum, pageSize);
        return ResultUtils.success(data);
    }

    @GetMapping("/detail")
    @Operation(summary = "实体详情（含全部属性）")
    public BaseResponse<Map<String, Object>> getEntityDetail(@RequestParam String nodeId) {
        ThrowUtils.throwIf(StrUtil.isBlank(nodeId), ErrorCode.PARAMS_ERROR, "nodeId 为空");
        Map<String, Object> data = neo4jService.getEntityDetail(nodeId);
        ThrowUtils.throwIf(data == null, ErrorCode.NOT_FOUND_ERROR, "实体不存在");
        return ResultUtils.success(data);
    }

    @PostMapping("/add")
    @Operation(summary = "新增实体")
    public BaseResponse<Map<String, Object>> createEntity(@RequestBody EntityNeo4jAddRequest request) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        ThrowUtils.throwIf(request.getModelId() == null || request.getModelId() <= 0, ErrorCode.PARAMS_ERROR, "modelId 为空");
        ThrowUtils.throwIf(StrUtil.isBlank(request.getName()), ErrorCode.PARAMS_ERROR, "实体名称为空");
        ThrowUtils.throwIf(StrUtil.isBlank(request.getType()), ErrorCode.PARAMS_ERROR, "实体类型为空");
        Map<String, Object> data = neo4jService.createEntity(
                request.getModelId(), request.getName(), request.getType(), request.getProperties());
        return ResultUtils.success(data);
    }

    @PostMapping("/update")
    @Operation(summary = "更新实体（名称和类型）")
    public BaseResponse<Map<String, Object>> updateEntity(@RequestBody EntityNeo4jUpdateRequest request) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        ThrowUtils.throwIf(StrUtil.isBlank(request.getNodeId()), ErrorCode.PARAMS_ERROR, "nodeId 为空");
        ThrowUtils.throwIf(StrUtil.isBlank(request.getName()), ErrorCode.PARAMS_ERROR, "实体名称为空");
        ThrowUtils.throwIf(StrUtil.isBlank(request.getType()), ErrorCode.PARAMS_ERROR, "实体类型为空");
        Map<String, Object> data = neo4jService.updateEntity(request.getNodeId(), request.getName(), request.getType());
        ThrowUtils.throwIf(data == null, ErrorCode.NOT_FOUND_ERROR, "实体不存在");
        return ResultUtils.success(data);
    }

    @PostMapping("/delete")
    @Operation(summary = "删除实体（含关联关系）")
    public BaseResponse<Boolean> deleteEntity(@RequestBody EntityNeo4jNodeIdRequest request) {
        ThrowUtils.throwIf(request == null || StrUtil.isBlank(request.getNodeId()), ErrorCode.PARAMS_ERROR, "nodeId 为空");
        boolean result = neo4jService.deleteEntity(request.getNodeId());
        return ResultUtils.success(result);
    }

    @PostMapping("/property/set")
    @Operation(summary = "设置实体属性（新增或更新）")
    public BaseResponse<Map<String, Object>> setProperty(@RequestBody EntityPropertySetRequest request) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        ThrowUtils.throwIf(StrUtil.isBlank(request.getNodeId()), ErrorCode.PARAMS_ERROR, "nodeId 为空");
        ThrowUtils.throwIf(StrUtil.isBlank(request.getKey()), ErrorCode.PARAMS_ERROR, "属性名为空");
        Map<String, Object> data = neo4jService.setEntityProperty(request.getNodeId(), request.getKey(), request.getValue());
        ThrowUtils.throwIf(data == null, ErrorCode.NOT_FOUND_ERROR, "实体不存在");
        return ResultUtils.success(data);
    }

    @PostMapping("/property/delete")
    @Operation(summary = "删除实体属性")
    public BaseResponse<Boolean> removeProperty(@RequestBody EntityPropertyDeleteRequest request) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        ThrowUtils.throwIf(StrUtil.isBlank(request.getNodeId()), ErrorCode.PARAMS_ERROR, "nodeId 为空");
        ThrowUtils.throwIf(StrUtil.isBlank(request.getKey()), ErrorCode.PARAMS_ERROR, "属性名为空");
        boolean result = neo4jService.removeEntityProperty(request.getNodeId(), request.getKey());
        return ResultUtils.success(result);
    }
}
