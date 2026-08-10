package com.yuan.seedboot.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.yuan.seedboot.model.entity.GraphRelationProperty;
import com.yuan.seedboot.model.entity.GraphRelationType;
import com.yuan.seedboot.model.request.RelationTypeAddRequest;
import com.yuan.seedboot.model.request.RelationTypeUpdateRequest;

import java.util.List;

/**
 * @description 针对表【graph_relation_type(关系类型)】的数据库操作Service
 */
public interface GraphRelationTypeService extends IService<GraphRelationType> {

    /**
     * 新增关系类型
     */
    GraphRelationType addRelationType(RelationTypeAddRequest request);

    /**
     * 编辑关系类型
     */
    boolean updateRelationType(RelationTypeUpdateRequest request);

    /**
     * 删除关系类型（级联删除属性）
     */
    boolean deleteRelationType(Long id);

    /**
     * 按 modelId 查询关系类型列表
     */
    List<GraphRelationType> listByModelId(Long modelId);

    /**
     * 按 relationTypeId 查询属性列表
     */
    List<GraphRelationProperty> listProperties(Long relationTypeId);
}
