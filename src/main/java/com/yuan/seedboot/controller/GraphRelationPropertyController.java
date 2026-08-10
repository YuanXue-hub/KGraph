package com.yuan.seedboot.controller;

import com.yuan.seedboot.common.BaseResponse;
import com.yuan.seedboot.common.DeleteRequest;
import com.yuan.seedboot.common.ResultUtils;
import com.yuan.seedboot.exception.ErrorCode;
import com.yuan.seedboot.exception.ThrowUtils;
import com.yuan.seedboot.model.entity.GraphRelationProperty;
import com.yuan.seedboot.model.request.RelationPropertyAddRequest;
import com.yuan.seedboot.model.request.RelationPropertyUpdateRequest;
import com.yuan.seedboot.service.GraphRelationPropertyService;
import io.swagger.v3.oas.annotations.Operation;
import jakarta.annotation.Resource;
import org.springframework.web.bind.annotation.*;

/**
 * 关系属性 Controller
 */
@RestController
@RequestMapping("/relationProperty")
public class GraphRelationPropertyController {

    @Resource
    private GraphRelationPropertyService graphRelationPropertyService;

    @PostMapping("/add")
    @Operation(summary = "新增关系属性")
    public BaseResponse<GraphRelationProperty> addProperty(@RequestBody RelationPropertyAddRequest request) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        GraphRelationProperty property = graphRelationPropertyService.addProperty(request);
        return ResultUtils.success(property);
    }

    @PostMapping("/delete")
    @Operation(summary = "删除关系属性")
    public BaseResponse<Boolean> deleteProperty(@RequestBody DeleteRequest request) {
        ThrowUtils.throwIf(request == null || request.getId() <= 0, ErrorCode.PARAMS_ERROR);
        boolean result = graphRelationPropertyService.deleteProperty(request.getId());
        return ResultUtils.success(result);
    }

    @PostMapping("/update")
    @Operation(summary = "更新关系属性")
    public BaseResponse<GraphRelationProperty> updateProperty(@RequestBody RelationPropertyUpdateRequest request) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        GraphRelationProperty property = graphRelationPropertyService.updateProperty(request);
        return ResultUtils.success(property);
    }
}
