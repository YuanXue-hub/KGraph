package com.yuan.seedboot.service;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.IService;
import com.yuan.seedboot.model.entity.GraphModel;
import com.yuan.seedboot.model.entity.User;
import com.yuan.seedboot.model.request.GraphModelAddRequest;
import com.yuan.seedboot.model.request.GraphModelCopyRequest;
import com.yuan.seedboot.model.request.GraphModelQueryRequest;
import com.yuan.seedboot.model.request.GraphModelUpdateRequest;
import com.yuan.seedboot.model.vo.GraphModelVO;

/**
 * @description 针对表【graph_model(图谱模型)】的数据库操作Service
 */
public interface GraphModelService extends IService<GraphModel> {

    /**
     * 新建图谱模型
     */
    GraphModel addModel(GraphModelAddRequest request, User loginUser);

    /**
     * 编辑图谱模型
     */
    boolean updateModel(GraphModelUpdateRequest request);

    /**
     * 分页查询模型列表
     */
    Page<GraphModel> listModels(GraphModelQueryRequest request);

    /**
     * 删除模型
     */
    boolean deleteModel(Long id);

    /**
     * 清空模型下所有实体类型和关系类型
     */
    boolean clearModel(Long id);

    /**
     * 复制模型（含实体/关系/属性）
     */
    boolean copyModel(GraphModelCopyRequest request, User loginUser);

    /**
     * 获取模型详情（含实体类型+属性+关系类型+属性）
     */
    GraphModelVO getModelDetail(Long modelId);

    /**
     * 更新 entityCount/relationCount 缓存
     */
    void updateModelCount(Long modelId);
}
