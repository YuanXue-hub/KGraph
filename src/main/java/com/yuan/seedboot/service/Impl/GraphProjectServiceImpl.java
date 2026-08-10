package com.yuan.seedboot.service.Impl;

import cn.hutool.core.util.ObjUtil;
import cn.hutool.core.util.StrUtil;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.yuan.seedboot.exception.BusinessException;
import com.yuan.seedboot.exception.ErrorCode;
import com.yuan.seedboot.exception.ThrowUtils;
import com.yuan.seedboot.mapper.GraphProjectMapper;
import com.yuan.seedboot.model.entity.GraphProject;
import com.yuan.seedboot.model.entity.User;
import com.yuan.seedboot.model.request.GraphProjectAddRequest;
import com.yuan.seedboot.model.request.GraphProjectQueryRequest;
import com.yuan.seedboot.model.request.GraphProjectUpdateRequest;
import com.yuan.seedboot.service.GraphProjectService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Service;

/**
 * @description 针对表【graph_project(图谱项目)】的数据库操作Service实现
 */
@Slf4j
@Service
public class GraphProjectServiceImpl extends ServiceImpl<GraphProjectMapper, GraphProject>
        implements GraphProjectService {

    @Override
    public GraphProject addProject(GraphProjectAddRequest request, User loginUser) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        ThrowUtils.throwIf(StrUtil.isBlank(request.getProjectName()), ErrorCode.PARAMS_ERROR, "项目名称为空");
        GraphProject project = new GraphProject();
        BeanUtils.copyProperties(request, project);
        project.setStorageEngine("neo4j");
        project.setIsConfiguredStorage(0);
        project.setIsGraphSpaceCreated(0);
        project.setCreateBy(loginUser.getId());
        boolean result = this.save(project);
        ThrowUtils.throwIf(!result, ErrorCode.OPERATION_ERROR, "新建项目失败");
        return project;
    }

    @Override
    public boolean updateProject(GraphProjectUpdateRequest request) {
        ThrowUtils.throwIf(request == null || request.getId() == null, ErrorCode.PARAMS_ERROR);
        GraphProject project = new GraphProject();
        BeanUtils.copyProperties(request, project);
        boolean result = this.updateById(project);
        ThrowUtils.throwIf(!result, ErrorCode.OPERATION_ERROR, "编辑项目失败");
        return true;
    }

    @Override
    public Page<GraphProject> listProjects(GraphProjectQueryRequest request) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        long current = request.getPageNum();
        long pageSize = request.getPageSize();
        String projectName = request.getProjectName();
        String sortField = request.getSortField();
        String sortOrder = request.getSortOrder();
        QueryWrapper<GraphProject> queryWrapper = new QueryWrapper<>();
        queryWrapper.like(StrUtil.isNotBlank(projectName), "projectName", projectName);
        queryWrapper.orderBy(StrUtil.isNotBlank(sortField), "ascend".equals(sortOrder), sortField);
        return this.page(new Page<>(current, pageSize), queryWrapper);
    }

    @Override
    public boolean deleteProject(Long id) {
        ThrowUtils.throwIf(id == null || id <= 0, ErrorCode.PARAMS_ERROR);
        GraphProject project = this.getById(id);
        ThrowUtils.throwIf(ObjUtil.isNull(project), ErrorCode.NOT_FOUND_ERROR, "项目不存在");
        return this.removeById(id);
    }
}
