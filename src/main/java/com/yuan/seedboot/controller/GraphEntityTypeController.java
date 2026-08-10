package com.yuan.seedboot.controller;

import com.yuan.seedboot.common.BaseResponse;
import com.yuan.seedboot.common.DeleteRequest;
import com.yuan.seedboot.common.ResultUtils;
import com.yuan.seedboot.exception.ErrorCode;
import com.yuan.seedboot.exception.ThrowUtils;
import com.yuan.seedboot.model.entity.GraphEntityProperty;
import com.yuan.seedboot.model.entity.GraphEntityType;
import com.yuan.seedboot.model.request.EntityTypeAddRequest;
import com.yuan.seedboot.model.request.EntityTypeUpdateRequest;
import com.yuan.seedboot.service.GraphEntityTypeService;
import io.swagger.v3.oas.annotations.Operation;
import jakarta.annotation.Resource;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 实体类型 Controller
 */
@RestController
@RequestMapping("/entityType")
public class GraphEntityTypeController {

    @Resource
    private GraphEntityTypeService graphEntityTypeService;

    @PostMapping("/add")
    @Operation(summary = "新增实体类型")
    public BaseResponse<GraphEntityType> addEntityType(@RequestBody EntityTypeAddRequest request) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        GraphEntityType entityType = graphEntityTypeService.addEntityType(request);
        return ResultUtils.success(entityType);
    }

    @PostMapping("/update")
    @Operation(summary = "编辑实体类型")
    public BaseResponse<Boolean> updateEntityType(@RequestBody EntityTypeUpdateRequest request) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        boolean result = graphEntityTypeService.updateEntityType(request);
        return ResultUtils.success(result);
    }

    @PostMapping("/delete")
    @Operation(summary = "删除实体类型")
    public BaseResponse<Boolean> deleteEntityType(@RequestBody DeleteRequest request) {
        ThrowUtils.throwIf(request == null || request.getId() <= 0, ErrorCode.PARAMS_ERROR);
        boolean result = graphEntityTypeService.deleteEntityType(request.getId());
        return ResultUtils.success(result);
    }

    @GetMapping("/list")
    @Operation(summary = "按 modelId 查实体类型列表")
    public BaseResponse<List<GraphEntityType>> listEntityType(long modelId) {
        ThrowUtils.throwIf(modelId <= 0, ErrorCode.PARAMS_ERROR);
        List<GraphEntityType> list = graphEntityTypeService.listByModelId(modelId);
        return ResultUtils.success(list);
    }

    @GetMapping("/properties")
    @Operation(summary = "按 entityTypeId 查属性列表")
    public BaseResponse<List<GraphEntityProperty>> listProperties(long entityTypeId) {
        ThrowUtils.throwIf(entityTypeId <= 0, ErrorCode.PARAMS_ERROR);
        List<GraphEntityProperty> list = graphEntityTypeService.listProperties(entityTypeId);
        return ResultUtils.success(list);
    }
}
