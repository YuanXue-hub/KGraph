package com.yuan.seedboot.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.yuan.seedboot.model.entity.GraphEntityProperty;
import com.yuan.seedboot.model.entity.GraphEntityType;
import com.yuan.seedboot.model.request.EntityPropertyAddRequest;
import com.yuan.seedboot.model.request.EntityTypeAddRequest;
import com.yuan.seedboot.model.request.EntityTypeUpdateRequest;

import java.util.List;

/**
 * @description 针对表【graph_entity_type(实体类型)】的数据库操作Service
 */
public interface GraphEntityTypeService extends IService<GraphEntityType> {

    /**
     * 新增实体类型
     */
    GraphEntityType addEntityType(EntityTypeAddRequest request);

    /**
     * 编辑实体类型
     */
    boolean updateEntityType(EntityTypeUpdateRequest request);

    /**
     * 删除实体类型（级联删除属性 + 关联关系类型）
     */
    boolean deleteEntityType(Long id);

    /**
     * 按 modelId 查询实体类型列表
     */
    List<GraphEntityType> listByModelId(Long modelId);

    /**
     * 按 entityTypeId 查询属性列表
     */
    List<GraphEntityProperty> listProperties(Long entityTypeId);
}
