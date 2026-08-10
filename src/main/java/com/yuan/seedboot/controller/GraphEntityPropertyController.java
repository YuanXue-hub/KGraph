package com.yuan.seedboot.controller;

import com.yuan.seedboot.common.BaseResponse;
import com.yuan.seedboot.common.DeleteRequest;
import com.yuan.seedboot.common.ResultUtils;
import com.yuan.seedboot.exception.ErrorCode;
import com.yuan.seedboot.exception.ThrowUtils;
import com.yuan.seedboot.model.entity.GraphEntityProperty;
import com.yuan.seedboot.model.request.EntityPropertyAddRequest;
import com.yuan.seedboot.model.request.EntityPropertyUpdateRequest;
import com.yuan.seedboot.service.GraphEntityPropertyService;
import io.swagger.v3.oas.annotations.Operation;
import jakarta.annotation.Resource;
import org.springframework.web.bind.annotation.*;

/**
 * 实体属性 Controller
 */
@RestController
@RequestMapping("/entityProperty")
public class GraphEntityPropertyController {

    @Resource
    private GraphEntityPropertyService graphEntityPropertyService;

    @PostMapping("/add")
    @Operation(summary = "新增实体属性")
    public BaseResponse<GraphEntityProperty> addProperty(@RequestBody EntityPropertyAddRequest request) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        GraphEntityProperty property = graphEntityPropertyService.addProperty(request);
        return ResultUtils.success(property);
    }

    @PostMapping("/delete")
    @Operation(summary = "删除实体属性")
    public BaseResponse<Boolean> deleteProperty(@RequestBody DeleteRequest request) {
        ThrowUtils.throwIf(request == null || request.getId() <= 0, ErrorCode.PARAMS_ERROR);
        boolean result = graphEntityPropertyService.deleteProperty(request.getId());
        return ResultUtils.success(result);
    }

    @PostMapping("/update")
    @Operation(summary = "更新实体属性")
    public BaseResponse<GraphEntityProperty> updateProperty(@RequestBody EntityPropertyUpdateRequest request) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        GraphEntityProperty property = graphEntityPropertyService.updateProperty(request);
        return ResultUtils.success(property);
    }
}
