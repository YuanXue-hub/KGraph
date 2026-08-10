package com.yuan.seedboot.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.yuan.seedboot.model.entity.GraphEntityProperty;
import com.yuan.seedboot.model.request.EntityPropertyAddRequest;
import com.yuan.seedboot.model.request.EntityPropertyUpdateRequest;

/**
 * @description 针对表【graph_entity_property(实体属性)】的数据库操作Service
 */
public interface GraphEntityPropertyService extends IService<GraphEntityProperty> {

    /**
     * 新增实体属性
     */
    GraphEntityProperty addProperty(EntityPropertyAddRequest request);

    /**
     * 更新实体属性
     */
    GraphEntityProperty updateProperty(EntityPropertyUpdateRequest request);

    /**
     * 删除实体属性
     */
    boolean deleteProperty(Long id);
}
