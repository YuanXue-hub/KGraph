package com.yuan.seedboot.service.Impl;

import cn.hutool.core.util.ObjUtil;
import cn.hutool.core.util.StrUtil;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.yuan.seedboot.exception.ErrorCode;
import com.yuan.seedboot.exception.ThrowUtils;
import com.yuan.seedboot.mapper.GraphEntityPropertyMapper;
import com.yuan.seedboot.model.entity.GraphEntityProperty;
import com.yuan.seedboot.model.request.EntityPropertyAddRequest;
import com.yuan.seedboot.model.request.EntityPropertyUpdateRequest;
import com.yuan.seedboot.service.GraphEntityPropertyService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Service;

/**
 * @description 针对表【graph_entity_property(实体属性)】的数据库操作Service实现
 */
@Slf4j
@Service
public class GraphEntityPropertyServiceImpl extends ServiceImpl<GraphEntityPropertyMapper, GraphEntityProperty>
        implements GraphEntityPropertyService {

    @Override
    public GraphEntityProperty addProperty(EntityPropertyAddRequest request) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        ThrowUtils.throwIf(request.getEntityTypeId() == null, ErrorCode.PARAMS_ERROR, "实体类型 id 为空");
        ThrowUtils.throwIf(StrUtil.isBlank(request.getPropertyName()), ErrorCode.PARAMS_ERROR, "属性名称为空");
        ThrowUtils.throwIf(StrUtil.isBlank(request.getPropertyType()), ErrorCode.PARAMS_ERROR, "属性类型为空");
        GraphEntityProperty property = new GraphEntityProperty();
        BeanUtils.copyProperties(request, property);
        property.setIsRequired(ObjUtil.defaultIfNull(property.getIsRequired(), 0));
        property.setSortOrder(ObjUtil.defaultIfNull(property.getSortOrder(), 0));
        boolean result = this.save(property);
        ThrowUtils.throwIf(!result, ErrorCode.OPERATION_ERROR, "新增实体属性失败");
        return property;
    }

    @Override
    public boolean deleteProperty(Long id) {
        ThrowUtils.throwIf(id == null || id <= 0, ErrorCode.PARAMS_ERROR);
        return this.removeById(id);
    }

    @Override
    public GraphEntityProperty updateProperty(EntityPropertyUpdateRequest request) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        ThrowUtils.throwIf(request.getId() == null || request.getId() <= 0, ErrorCode.PARAMS_ERROR, "属性 id 为空");
        ThrowUtils.throwIf(StrUtil.isBlank(request.getPropertyName()), ErrorCode.PARAMS_ERROR, "属性名称为空");
        ThrowUtils.throwIf(StrUtil.isBlank(request.getPropertyType()), ErrorCode.PARAMS_ERROR, "属性类型为空");
        GraphEntityProperty property = this.getById(request.getId());
        ThrowUtils.throwIf(property == null, ErrorCode.NOT_FOUND_ERROR, "实体属性不存在");
        property.setPropertyName(request.getPropertyName());
        property.setPropertyType(request.getPropertyType());
        property.setIsRequired(ObjUtil.defaultIfNull(request.getIsRequired(), 0));
        property.setDefaultValue(request.getDefaultValue());
        property.setDescription(request.getDescription());
        boolean result = this.updateById(property);
        ThrowUtils.throwIf(!result, ErrorCode.OPERATION_ERROR, "更新实体属性失败");
        return property;
    }
}
