package com.yuan.seedboot.controller;

import cn.hutool.core.util.StrUtil;
import com.yuan.seedboot.common.BaseResponse;
import com.yuan.seedboot.common.ResultUtils;
import com.yuan.seedboot.exception.ErrorCode;
import com.yuan.seedboot.exception.ThrowUtils;
import com.yuan.seedboot.model.request.EntityPropertyDeleteRequest;
import com.yuan.seedboot.model.request.EntityPropertySetRequest;
import com.yuan.seedboot.model.request.EntityNeo4jNodeIdRequest;
import com.yuan.seedboot.service.Neo4jService;
import io.swagger.v3.oas.annotations.Operation;
import jakarta.annotation.Resource;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * Neo4j 关系管理 Controller
 * <p>
 * 提供图谱模型下关系和关系属性的增删改查，直接操作 Neo4j 数据层。
 */
@RestController
@RequestMapping("/relation")
public class GraphRelationController {

    @Resource
    private Neo4jService neo4jService;

    @GetMapping("/list")
    @Operation(summary = "关系列表（按 modelId 分页）")
    public BaseResponse<Map<String, Object>> listRelations(
            long modelId,
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "10") int pageSize) {
        ThrowUtils.throwIf(modelId <= 0, ErrorCode.PARAMS_ERROR);
        ThrowUtils.throwIf(pageNum <= 0 || pageSize <= 0 || pageSize > 500, ErrorCode.PARAMS_ERROR, "分页参数有误");
        Map<String, Object> data = neo4jService.listRelations(modelId, keyword, pageNum, pageSize);
        return ResultUtils.success(data);
    }

    @GetMapping("/detail")
    @Operation(summary = "关系详情（含全部属性）")
    public BaseResponse<Map<String, Object>> getRelationDetail(@RequestParam String relId) {
        ThrowUtils.throwIf(StrUtil.isBlank(relId), ErrorCode.PARAMS_ERROR, "relId 为空");
        Map<String, Object> data = neo4jService.getRelationDetail(relId);
        ThrowUtils.throwIf(data == null, ErrorCode.NOT_FOUND_ERROR, "关系不存在");
        return ResultUtils.success(data);
    }

    @PostMapping("/delete")
    @Operation(summary = "删除关系")
    public BaseResponse<Boolean> deleteRelation(@RequestBody EntityNeo4jNodeIdRequest request) {
        ThrowUtils.throwIf(request == null || StrUtil.isBlank(request.getNodeId()), ErrorCode.PARAMS_ERROR, "relId 为空");
        boolean result = neo4jService.deleteRelation(request.getNodeId());
        return ResultUtils.success(result);
    }

    @PostMapping("/property/set")
    @Operation(summary = "设置关系属性（新增或更新）")
    public BaseResponse<Map<String, Object>> setRelationProperty(@RequestBody EntityPropertySetRequest request) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        ThrowUtils.throwIf(StrUtil.isBlank(request.getNodeId()), ErrorCode.PARAMS_ERROR, "relId 为空");
        ThrowUtils.throwIf(StrUtil.isBlank(request.getKey()), ErrorCode.PARAMS_ERROR, "属性名为空");
        Map<String, Object> data = neo4jService.setRelationProperty(request.getNodeId(), request.getKey(), request.getValue());
        ThrowUtils.throwIf(data == null, ErrorCode.NOT_FOUND_ERROR, "关系不存在");
        return ResultUtils.success(data);
    }

    @PostMapping("/property/delete")
    @Operation(summary = "删除关系属性")
    public BaseResponse<Boolean> removeRelationProperty(@RequestBody EntityPropertyDeleteRequest request) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        ThrowUtils.throwIf(StrUtil.isBlank(request.getNodeId()), ErrorCode.PARAMS_ERROR, "relId 为空");
        ThrowUtils.throwIf(StrUtil.isBlank(request.getKey()), ErrorCode.PARAMS_ERROR, "属性名为空");
        boolean result = neo4jService.removeRelationProperty(request.getNodeId(), request.getKey());
        return ResultUtils.success(result);
    }
}
