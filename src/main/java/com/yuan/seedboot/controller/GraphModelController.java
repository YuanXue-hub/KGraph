package com.yuan.seedboot.controller;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.yuan.seedboot.common.BaseResponse;
import com.yuan.seedboot.common.DeleteRequest;
import com.yuan.seedboot.common.ResultUtils;
import com.yuan.seedboot.exception.ErrorCode;
import com.yuan.seedboot.exception.ThrowUtils;
import com.yuan.seedboot.model.entity.GraphModel;
import com.yuan.seedboot.model.entity.User;
import com.yuan.seedboot.model.request.GraphModelAddRequest;
import com.yuan.seedboot.model.request.GraphModelCopyRequest;
import com.yuan.seedboot.model.request.GraphModelQueryRequest;
import com.yuan.seedboot.model.request.GraphModelUpdateRequest;
import com.yuan.seedboot.model.vo.GraphModelVO;
import com.yuan.seedboot.service.GraphModelService;
import com.yuan.seedboot.service.Neo4jService;
import com.yuan.seedboot.service.UserService;
import io.swagger.v3.oas.annotations.Operation;
import jakarta.annotation.Resource;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.web.bind.annotation.*;

import java.util.*;
import java.util.stream.Collectors;

/**
 * 图谱模型 Controller
 */
@RestController
@RequestMapping("/model")
public class GraphModelController {

    @Resource
    private GraphModelService graphModelService;

    @Resource
    private UserService userService;

    @Resource
    private Neo4jService neo4jService;

    @PostMapping("/add")
    @Operation(summary = "新建模型")
    public BaseResponse<GraphModel> addModel(@RequestBody GraphModelAddRequest request, HttpServletRequest httpRequest) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        User loginUser = userService.getLoginUser(httpRequest);
        GraphModel model = graphModelService.addModel(request, loginUser);
        return ResultUtils.success(model);
    }

    @PostMapping("/update")
    @Operation(summary = "编辑模型")
    public BaseResponse<Boolean> updateModel(@RequestBody GraphModelUpdateRequest request) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        boolean result = graphModelService.updateModel(request);
        return ResultUtils.success(result);
    }

    @PostMapping("/delete")
    @Operation(summary = "删除模型")
    public BaseResponse<Boolean> deleteModel(@RequestBody DeleteRequest request) {
        ThrowUtils.throwIf(request == null || request.getId() <= 0, ErrorCode.PARAMS_ERROR);
        boolean result = graphModelService.deleteModel(request.getId());
        return ResultUtils.success(result);
    }

    @PostMapping("/clear")
    @Operation(summary = "清空模型")
    public BaseResponse<Boolean> clearModel(@RequestBody DeleteRequest request) {
        ThrowUtils.throwIf(request == null || request.getId() <= 0, ErrorCode.PARAMS_ERROR);
        boolean result = graphModelService.clearModel(request.getId());
        return ResultUtils.success(result);
    }

    @PostMapping("/copy")
    @Operation(summary = "复制模型")
    public BaseResponse<Boolean> copyModel(@RequestBody GraphModelCopyRequest request, HttpServletRequest httpRequest) {
        ThrowUtils.throwIf(request == null || request.getId() == null || request.getId() <= 0, ErrorCode.PARAMS_ERROR);
        User loginUser = userService.getLoginUser(httpRequest);
        boolean result = graphModelService.copyModel(request, loginUser);
        return ResultUtils.success(result);
    }

    @GetMapping("/list")
    @Operation(summary = "模型列表（按 projectId 分页）")
    public BaseResponse<Page<GraphModel>> listModels(GraphModelQueryRequest request) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        Page<GraphModel> page = graphModelService.listModels(request);
        // 批量填充创建人姓名
        fillCreateByName(page.getRecords());
        // 从 Neo4j 实时查询实体/关系数量
        fillNeo4jCounts(page.getRecords());
        return ResultUtils.success(page);
    }

    /**
     * 批量填充模型列表的创建人姓名
     */
    private void fillCreateByName(List<GraphModel> records) {
        if (records == null || records.isEmpty()) {
            return;
        }
        Set<Long> userIds = records.stream()
                .map(GraphModel::getCreateBy)
                .filter(Objects::nonNull)
                .collect(Collectors.toSet());
        if (userIds.isEmpty()) {
            return;
        }
        Map<Long, String> idToName = userService.listByIds(userIds).stream()
                .collect(Collectors.toMap(User::getId, User::getUserName, (a, b) -> a));
        records.forEach(m -> m.setCreateByName(idToName.get(m.getCreateBy())));
    }

    /**
     * 从 Neo4j 实时查询并填充模型的实体数/关系数
     */
    private void fillNeo4jCounts(List<GraphModel> records) {
        if (records == null || records.isEmpty()) {
            return;
        }
        List<Long> modelIds = records.stream()
                .map(GraphModel::getId)
                .filter(Objects::nonNull)
                .collect(Collectors.toList());
        if (modelIds.isEmpty()) {
            return;
        }
        Map<Long, long[]> counts = neo4jService.getCountsForModels(modelIds);
        records.forEach(m -> {
            long[] arr = counts.get(m.getId());
            if (arr != null) {
                m.setEntityCount((int) arr[0]);
                m.setRelationCount((int) arr[1]);
            }
        });
    }

    @GetMapping("/detail")
    @Operation(summary = "模型详情（含实体/关系类型）")
    public BaseResponse<GraphModelVO> getModelDetail(long modelId) {
        ThrowUtils.throwIf(modelId <= 0, ErrorCode.PARAMS_ERROR);
        GraphModelVO vo = graphModelService.getModelDetail(modelId);
        return ResultUtils.success(vo);
    }
}
