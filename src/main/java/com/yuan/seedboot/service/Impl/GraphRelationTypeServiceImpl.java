package com.yuan.seedboot.service.Impl;

import cn.hutool.core.collection.CollUtil;
import cn.hutool.core.util.ObjUtil;
import cn.hutool.core.util.StrUtil;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.yuan.seedboot.exception.ErrorCode;
import com.yuan.seedboot.exception.ThrowUtils;
import com.yuan.seedboot.mapper.GraphRelationTypeMapper;
import com.yuan.seedboot.model.entity.GraphRelationProperty;
import com.yuan.seedboot.model.entity.GraphRelationType;
import com.yuan.seedboot.model.request.RelationTypeAddRequest;
import com.yuan.seedboot.model.request.RelationTypeUpdateRequest;
import com.yuan.seedboot.service.GraphRelationPropertyService;
import com.yuan.seedboot.service.GraphRelationTypeService;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/**
 * @description 针对表【graph_relation_type(关系类型)】的数据库操作Service实现
 */
@Slf4j
@Service
public class GraphRelationTypeServiceImpl extends ServiceImpl<GraphRelationTypeMapper, GraphRelationType>
        implements GraphRelationTypeService {

    @Resource
    private GraphRelationPropertyService graphRelationPropertyService;

    @Override
    public GraphRelationType addRelationType(RelationTypeAddRequest request) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        ThrowUtils.throwIf(request.getModelId() == null, ErrorCode.PARAMS_ERROR, "模型 id 为空");
        ThrowUtils.throwIf(StrUtil.isBlank(request.getRelationName()), ErrorCode.PARAMS_ERROR, "关系名称为空");
        ThrowUtils.throwIf(request.getSourceEntityTypeId() == null, ErrorCode.PARAMS_ERROR, "起始实体类型 id 为空");
        ThrowUtils.throwIf(request.getTargetEntityTypeId() == null, ErrorCode.PARAMS_ERROR, "终止实体类型 id 为空");
        GraphRelationType relationType = new GraphRelationType();
        BeanUtils.copyProperties(request, relationType);
        relationType.setSortOrder(ObjUtil.defaultIfNull(relationType.getSortOrder(), 0));
        boolean result = this.save(relationType);
        ThrowUtils.throwIf(!result, ErrorCode.OPERATION_ERROR, "新增关系类型失败");
        return relationType;
    }

    @Override
    public boolean updateRelationType(RelationTypeUpdateRequest request) {
        ThrowUtils.throwIf(request == null || request.getId() == null, ErrorCode.PARAMS_ERROR);
        GraphRelationType relationType = new GraphRelationType();
        BeanUtils.copyProperties(request, relationType);
        boolean result = this.updateById(relationType);
        ThrowUtils.throwIf(!result, ErrorCode.OPERATION_ERROR, "编辑关系类型失败");
        return true;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public boolean deleteRelationType(Long id) {
        ThrowUtils.throwIf(id == null || id <= 0, ErrorCode.PARAMS_ERROR);
        GraphRelationType relationType = this.getById(id);
        ThrowUtils.throwIf(ObjUtil.isNull(relationType), ErrorCode.NOT_FOUND_ERROR, "关系类型不存在");
        // 删除属性
        List<GraphRelationProperty> properties = listProperties(id);
        if (CollUtil.isNotEmpty(properties)) {
            for (GraphRelationProperty property : properties) {
                graphRelationPropertyService.deleteProperty(property.getId());
            }
        }
        return this.removeById(id);
    }

    @Override
    public List<GraphRelationType> listByModelId(Long modelId) {
        ThrowUtils.throwIf(modelId == null, ErrorCode.PARAMS_ERROR);
        QueryWrapper<GraphRelationType> queryWrapper = new QueryWrapper<>();
        queryWrapper.eq("modelId", modelId);
        queryWrapper.orderByAsc("sortOrder");
        return this.list(queryWrapper);
    }

    @Override
    public List<GraphRelationProperty> listProperties(Long relationTypeId) {
        ThrowUtils.throwIf(relationTypeId == null, ErrorCode.PARAMS_ERROR);
        QueryWrapper<GraphRelationProperty> queryWrapper = new QueryWrapper<>();
        queryWrapper.eq("relationTypeId", relationTypeId);
        queryWrapper.orderByAsc("sortOrder");
        return graphRelationPropertyService.list(queryWrapper);
    }
}
