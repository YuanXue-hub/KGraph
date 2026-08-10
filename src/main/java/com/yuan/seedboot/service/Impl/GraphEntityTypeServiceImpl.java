package com.yuan.seedboot.service.Impl;

import cn.hutool.core.collection.CollUtil;
import cn.hutool.core.util.ObjUtil;
import cn.hutool.core.util.StrUtil;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.yuan.seedboot.exception.BusinessException;
import com.yuan.seedboot.exception.ErrorCode;
import com.yuan.seedboot.exception.ThrowUtils;
import com.yuan.seedboot.mapper.GraphEntityTypeMapper;
import com.yuan.seedboot.model.entity.GraphEntityProperty;
import com.yuan.seedboot.model.entity.GraphEntityType;
import com.yuan.seedboot.model.entity.GraphRelationType;
import com.yuan.seedboot.model.request.EntityTypeAddRequest;
import com.yuan.seedboot.model.request.EntityTypeUpdateRequest;
import com.yuan.seedboot.service.GraphEntityPropertyService;
import com.yuan.seedboot.service.GraphEntityTypeService;
import com.yuan.seedboot.service.GraphRelationTypeService;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/**
 * @description 针对表【graph_entity_type(实体类型)】的数据库操作Service实现
 */
@Slf4j
@Service
public class GraphEntityTypeServiceImpl extends ServiceImpl<GraphEntityTypeMapper, GraphEntityType>
        implements GraphEntityTypeService {

    @Resource
    private GraphEntityPropertyService graphEntityPropertyService;

    @Resource
    private GraphRelationTypeService graphRelationTypeService;

    @Override
    public GraphEntityType addEntityType(EntityTypeAddRequest request) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        ThrowUtils.throwIf(request.getModelId() == null, ErrorCode.PARAMS_ERROR, "模型 id 为空");
        ThrowUtils.throwIf(StrUtil.isBlank(request.getEntityName()), ErrorCode.PARAMS_ERROR, "实体名称为空");
        GraphEntityType entityType = new GraphEntityType();
        BeanUtils.copyProperties(request, entityType);
        entityType.setSortOrder(ObjUtil.defaultIfNull(entityType.getSortOrder(), 0));
        boolean result = this.save(entityType);
        ThrowUtils.throwIf(!result, ErrorCode.OPERATION_ERROR, "新增实体类型失败");
        return entityType;
    }

    @Override
    public boolean updateEntityType(EntityTypeUpdateRequest request) {
        ThrowUtils.throwIf(request == null || request.getId() == null, ErrorCode.PARAMS_ERROR);
        GraphEntityType entityType = new GraphEntityType();
        BeanUtils.copyProperties(request, entityType);
        boolean result = this.updateById(entityType);
        ThrowUtils.throwIf(!result, ErrorCode.OPERATION_ERROR, "编辑实体类型失败");
        return true;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public boolean deleteEntityType(Long id) {
        ThrowUtils.throwIf(id == null || id <= 0, ErrorCode.PARAMS_ERROR);
        GraphEntityType entityType = this.getById(id);
        ThrowUtils.throwIf(ObjUtil.isNull(entityType), ErrorCode.NOT_FOUND_ERROR, "实体类型不存在");
        // 删除属性
        List<GraphEntityProperty> properties = listProperties(id);
        if (CollUtil.isNotEmpty(properties)) {
            for (GraphEntityProperty property : properties) {
                graphEntityPropertyService.deleteProperty(property.getId());
            }
        }
        // 删除引用了该实体类型的关系类型
        QueryWrapper<GraphRelationType> queryWrapper = new QueryWrapper<>();
        queryWrapper.eq("sourceEntityTypeId", id).or().eq("targetEntityTypeId", id);
        List<GraphRelationType> relationTypes = graphRelationTypeService.list(queryWrapper);
        if (CollUtil.isNotEmpty(relationTypes)) {
            for (GraphRelationType relationType : relationTypes) {
                graphRelationTypeService.deleteRelationType(relationType.getId());
            }
        }
        return this.removeById(id);
    }

    @Override
    public List<GraphEntityType> listByModelId(Long modelId) {
        ThrowUtils.throwIf(modelId == null, ErrorCode.PARAMS_ERROR);
        QueryWrapper<GraphEntityType> queryWrapper = new QueryWrapper<>();
        queryWrapper.eq("modelId", modelId);
        queryWrapper.orderByAsc("sortOrder");
        return this.list(queryWrapper);
    }

    @Override
    public List<GraphEntityProperty> listProperties(Long entityTypeId) {
        ThrowUtils.throwIf(entityTypeId == null, ErrorCode.PARAMS_ERROR);
        QueryWrapper<GraphEntityProperty> queryWrapper = new QueryWrapper<>();
        queryWrapper.eq("entityTypeId", entityTypeId);
        queryWrapper.orderByAsc("sortOrder");
        return graphEntityPropertyService.list(queryWrapper);
    }
}
