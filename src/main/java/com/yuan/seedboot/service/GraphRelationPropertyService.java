package com.yuan.seedboot.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.yuan.seedboot.model.entity.GraphRelationProperty;
import com.yuan.seedboot.model.request.RelationPropertyAddRequest;
import com.yuan.seedboot.model.request.RelationPropertyUpdateRequest;

/**
 * @description 针对表【graph_relation_property(关系属性)】的数据库操作Service
 */
public interface GraphRelationPropertyService extends IService<GraphRelationProperty> {

    /**
     * 新增关系属性
     */
    GraphRelationProperty addProperty(RelationPropertyAddRequest request);

    /**
     * 更新关系属性
     */
    GraphRelationProperty updateProperty(RelationPropertyUpdateRequest request);

    /**
     * 删除关系属性
     */
    boolean deleteProperty(Long id);
}
