package com.yuan.seedboot.controller;

import com.yuan.seedboot.common.BaseResponse;
import com.yuan.seedboot.common.ResultUtils;
import com.yuan.seedboot.exception.ErrorCode;
import com.yuan.seedboot.exception.ThrowUtils;
import com.yuan.seedboot.service.Neo4jService;
import io.swagger.v3.oas.annotations.Operation;
import jakarta.annotation.Resource;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * 图谱探索 Controller
 */
@RestController
@RequestMapping("/explore")
public class GraphExploreController {

    @Resource
    private Neo4jService neo4jService;

    @GetMapping("/nodes")
    @Operation(summary = "获取节点与边（按 modelId, 支持 limit）")
    public BaseResponse<Map<String, Object>> getNodes(long modelId,
                                                       @RequestParam(defaultValue = "100") int limit) {
        ThrowUtils.throwIf(modelId <= 0, ErrorCode.PARAMS_ERROR);
        ThrowUtils.throwIf(limit <= 0 || limit > 1000, ErrorCode.PARAMS_ERROR, "limit 范围 1-1000");
        Map<String, Object> data = neo4jService.getNodes(modelId, limit);
        return ResultUtils.success(data);
    }

    @GetMapping("/neighbors")
    @Operation(summary = "获取邻居节点与边（按 nodeId）")
    public BaseResponse<Map<String, Object>> getNeighbors(@RequestParam String nodeId) {
        ThrowUtils.throwIf(nodeId == null || nodeId.isBlank(), ErrorCode.PARAMS_ERROR);
        Map<String, Object> data = neo4jService.getNeighbors(nodeId);
        return ResultUtils.success(data);
    }

    @GetMapping("/search")
    @Operation(summary = "搜索节点（按名称模糊查询）")
    public BaseResponse<Map<String, Object>> searchNodes(long modelId,
                                                          @RequestParam String keyword) {
        ThrowUtils.throwIf(modelId <= 0, ErrorCode.PARAMS_ERROR);
        ThrowUtils.throwIf(keyword == null || keyword.isBlank(), ErrorCode.PARAMS_ERROR);
        Map<String, Object> data = neo4jService.searchNodes(modelId, keyword);
        return ResultUtils.success(data);
    }

    @GetMapping("/stats")
    @Operation(summary = "图谱统计（节点数、关系数、类型分布）")
    public BaseResponse<Map<String, Object>> getStats(long modelId) {
        ThrowUtils.throwIf(modelId <= 0, ErrorCode.PARAMS_ERROR);
        Map<String, Object> stats = neo4jService.getStats(modelId);
        return ResultUtils.success(stats);
    }
}
