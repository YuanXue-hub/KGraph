package com.yuan.seedboot.service;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.IService;
import com.yuan.seedboot.model.entity.GraphProject;
import com.yuan.seedboot.model.entity.User;
import com.yuan.seedboot.model.request.GraphProjectAddRequest;
import com.yuan.seedboot.model.request.GraphProjectUpdateRequest;
import com.yuan.seedboot.model.request.GraphProjectQueryRequest;

/**
 * @description 针对表【graph_project(图谱项目)】的数据库操作Service
 */
public interface GraphProjectService extends IService<GraphProject> {

    /**
     * 新建图谱项目
     */
    GraphProject addProject(GraphProjectAddRequest request, User loginUser);

    /**
     * 编辑图谱项目
     */
    boolean updateProject(GraphProjectUpdateRequest request);

    /**
     * 分页查询项目列表
     */
    Page<GraphProject> listProjects(GraphProjectQueryRequest request);

    /**
     * 删除项目
     */
    boolean deleteProject(Long id);
}
