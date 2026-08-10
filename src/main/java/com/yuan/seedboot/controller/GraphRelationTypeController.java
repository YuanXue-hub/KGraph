package com.yuan.seedboot.controller;

import com.yuan.seedboot.common.BaseResponse;
import com.yuan.seedboot.common.DeleteRequest;
import com.yuan.seedboot.common.ResultUtils;
import com.yuan.seedboot.exception.ErrorCode;
import com.yuan.seedboot.exception.ThrowUtils;
import com.yuan.seedboot.model.entity.GraphRelationProperty;
import com.yuan.seedboot.model.entity.GraphRelationType;
import com.yuan.seedboot.model.request.RelationTypeAddRequest;
import com.yuan.seedboot.model.request.RelationTypeUpdateRequest;
import com.yuan.seedboot.service.GraphRelationTypeService;
import io.swagger.v3.oas.annotations.Operation;
import jakarta.annotation.Resource;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 关系类型 Controller
 */
@RestController
@RequestMapping("/relationType")
public class GraphRelationTypeController {

    @Resource
    private GraphRelationTypeService graphRelationTypeService;

    @PostMapping("/add")
    @Operation(summary = "新增关系类型")
    public BaseResponse<GraphRelationType> addRelationType(@RequestBody RelationTypeAddRequest request) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        GraphRelationType relationType = graphRelationTypeService.addRelationType(request);
        return ResultUtils.success(relationType);
    }

    @PostMapping("/update")
    @Operation(summary = "编辑关系类型")
    public BaseResponse<Boolean> updateRelationType(@RequestBody RelationTypeUpdateRequest request) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        boolean result = graphRelationTypeService.updateRelationType(request);
        return ResultUtils.success(result);
    }

    @PostMapping("/delete")
    @Operation(summary = "删除关系类型")
    public BaseResponse<Boolean> deleteRelationType(@RequestBody DeleteRequest request) {
        ThrowUtils.throwIf(request == null || request.getId() <= 0, ErrorCode.PARAMS_ERROR);
        boolean result = graphRelationTypeService.deleteRelationType(request.getId());
        return ResultUtils.success(result);
    }

    @GetMapping("/list")
    @Operation(summary = "按 modelId 查关系类型列表")
    public BaseResponse<List<GraphRelationType>> listRelationType(long modelId) {
        ThrowUtils.throwIf(modelId <= 0, ErrorCode.PARAMS_ERROR);
        List<GraphRelationType> list = graphRelationTypeService.listByModelId(modelId);
        return ResultUtils.success(list);
    }

    @GetMapping("/properties")
    @Operation(summary = "按 relationTypeId 查属性列表")
    public BaseResponse<List<GraphRelationProperty>> listProperties(long relationTypeId) {
        ThrowUtils.throwIf(relationTypeId <= 0, ErrorCode.PARAMS_ERROR);
        List<GraphRelationProperty> list = graphRelationTypeService.listProperties(relationTypeId);
        return ResultUtils.success(list);
    }
}
