package com.yuan.seedboot.controller;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.yuan.seedboot.common.BaseResponse;
import com.yuan.seedboot.common.DeleteRequest;
import com.yuan.seedboot.common.ResultUtils;
import com.yuan.seedboot.exception.ErrorCode;
import com.yuan.seedboot.exception.ThrowUtils;
import com.yuan.seedboot.model.entity.GraphProject;
import com.yuan.seedboot.model.entity.User;
import com.yuan.seedboot.model.request.GraphProjectAddRequest;
import com.yuan.seedboot.model.request.GraphProjectQueryRequest;
import com.yuan.seedboot.model.request.GraphProjectUpdateRequest;
import com.yuan.seedboot.service.GraphProjectService;
import com.yuan.seedboot.service.UserService;
import io.swagger.v3.oas.annotations.Operation;
import jakarta.annotation.Resource;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.web.bind.annotation.*;

import java.util.*;
import java.util.stream.Collectors;

/**
 * 图谱项目 Controller
 */
@RestController
@RequestMapping("/project")
public class GraphProjectController {

    @Resource
    private GraphProjectService graphProjectService;

    @Resource
    private UserService userService;

    @PostMapping("/add")
    @Operation(summary = "新建项目")
    public BaseResponse<GraphProject> addProject(@RequestBody GraphProjectAddRequest request, HttpServletRequest httpRequest) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        User loginUser = userService.getLoginUser(httpRequest);
        GraphProject project = graphProjectService.addProject(request, loginUser);
        return ResultUtils.success(project);
    }

    @PostMapping("/update")
    @Operation(summary = "编辑项目")
    public BaseResponse<Boolean> updateProject(@RequestBody GraphProjectUpdateRequest request) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        boolean result = graphProjectService.updateProject(request);
        return ResultUtils.success(result);
    }

    @PostMapping("/delete")
    @Operation(summary = "删除项目")
    public BaseResponse<Boolean> deleteProject(@RequestBody DeleteRequest request) {
        ThrowUtils.throwIf(request == null || request.getId() <= 0, ErrorCode.PARAMS_ERROR);
        boolean result = graphProjectService.deleteProject(request.getId());
        return ResultUtils.success(result);
    }

    @GetMapping("/list")
    @Operation(summary = "项目列表（分页）")
    public BaseResponse<Page<GraphProject>> listProjects(GraphProjectQueryRequest request) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        Page<GraphProject> page = graphProjectService.listProjects(request);
        // 批量填充创建人姓名
        fillCreateByName(page.getRecords());
        return ResultUtils.success(page);
    }

    /**
     * 批量填充项目列表的创建人姓名
     */
    private void fillCreateByName(List<GraphProject> records) {
        if (records == null || records.isEmpty()) {
            return;
        }
        Set<Long> userIds = records.stream()
                .map(GraphProject::getCreateBy)
                .filter(Objects::nonNull)
                .collect(Collectors.toSet());
        if (userIds.isEmpty()) {
            return;
        }
        Map<Long, String> idToName = userService.listByIds(userIds).stream()
                .collect(Collectors.toMap(User::getId, User::getUserName, (a, b) -> a));
        records.forEach(p -> p.setCreateByName(idToName.get(p.getCreateBy())));
    }

    @GetMapping("/get")
    @Operation(summary = "项目详情")
    public BaseResponse<GraphProject> getProject(long id) {
        ThrowUtils.throwIf(id <= 0, ErrorCode.PARAMS_ERROR);
        GraphProject project = graphProjectService.getById(id);
        ThrowUtils.throwIf(project == null, ErrorCode.NOT_FOUND_ERROR);
        return ResultUtils.success(project);
    }
}
