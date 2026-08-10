package com.yuan.seedboot.service.Impl;

import cn.hutool.core.collection.CollUtil;
import cn.hutool.core.util.ObjUtil;
import cn.hutool.core.util.StrUtil;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.yuan.seedboot.exception.BusinessException;
import com.yuan.seedboot.exception.ErrorCode;
import com.yuan.seedboot.exception.ThrowUtils;
import com.yuan.seedboot.mapper.GraphModelMapper;
import com.yuan.seedboot.model.entity.*;
import com.yuan.seedboot.model.request.GraphModelAddRequest;
import com.yuan.seedboot.model.request.GraphModelCopyRequest;
import com.yuan.seedboot.model.request.GraphModelQueryRequest;
import com.yuan.seedboot.model.request.GraphModelUpdateRequest;
import com.yuan.seedboot.model.vo.EntityTypeVO;
import com.yuan.seedboot.model.vo.GraphModelVO;
import com.yuan.seedboot.model.vo.RelationTypeVO;
import com.yuan.seedboot.service.*;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * @description 针对表【graph_model(图谱模型)】的数据库操作Service实现
 */
@Slf4j
@Service
public class GraphModelServiceImpl extends ServiceImpl<GraphModelMapper, GraphModel>
        implements GraphModelService {

    @Resource
    private GraphEntityTypeService graphEntityTypeService;

    @Resource
    private GraphRelationTypeService graphRelationTypeService;

    @Resource
    private GraphEntityPropertyService graphEntityPropertyService;

    @Resource
    private GraphRelationPropertyService graphRelationPropertyService;

    @Override
    public GraphModel addModel(GraphModelAddRequest request, User loginUser) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        ThrowUtils.throwIf(request.getProjectId() == null, ErrorCode.PARAMS_ERROR, "项目 id 为空");
        ThrowUtils.throwIf(StrUtil.isBlank(request.getModelName()), ErrorCode.PARAMS_ERROR, "模型名称为空");
        GraphModel model = new GraphModel();
        BeanUtils.copyProperties(request, model);
        model.setVersion(ObjUtil.defaultIfNull(request.getVersion(), 1));
        model.setEntityCount(0);
        model.setRelationCount(0);
        model.setCreateBy(loginUser.getId());
        boolean result = this.save(model);
        ThrowUtils.throwIf(!result, ErrorCode.OPERATION_ERROR, "新建模型失败");
        return model;
    }

    @Override
    public boolean updateModel(GraphModelUpdateRequest request) {
        ThrowUtils.throwIf(request == null || request.getId() == null, ErrorCode.PARAMS_ERROR);
        GraphModel model = new GraphModel();
        BeanUtils.copyProperties(request, model);
        boolean result = this.updateById(model);
        ThrowUtils.throwIf(!result, ErrorCode.OPERATION_ERROR, "编辑模型失败");
        return true;
    }

    @Override
    public Page<GraphModel> listModels(GraphModelQueryRequest request) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        long current = request.getPageNum();
        long pageSize = request.getPageSize();
        Long projectId = request.getProjectId();
        String modelName = request.getModelName();
        String sortField = request.getSortField();
        String sortOrder = request.getSortOrder();
        QueryWrapper<GraphModel> queryWrapper = new QueryWrapper<>();
        queryWrapper.eq(ObjUtil.isNotNull(projectId), "projectId", projectId);
        queryWrapper.like(StrUtil.isNotBlank(modelName), "modelName", modelName);
        queryWrapper.orderBy(StrUtil.isNotBlank(sortField), "ascend".equals(sortOrder), sortField);
        return this.page(new Page<>(current, pageSize), queryWrapper);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public boolean deleteModel(Long id) {
        ThrowUtils.throwIf(id == null || id <= 0, ErrorCode.PARAMS_ERROR);
        GraphModel model = this.getById(id);
        ThrowUtils.throwIf(ObjUtil.isNull(model), ErrorCode.NOT_FOUND_ERROR, "模型不存在");
        // 级联清理实体类型+属性、关系类型+属性
        clearModelRelationsAndEntities(id);
        return this.removeById(id);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public boolean clearModel(Long id) {
        ThrowUtils.throwIf(id == null || id <= 0, ErrorCode.PARAMS_ERROR);
        GraphModel model = this.getById(id);
        ThrowUtils.throwIf(ObjUtil.isNull(model), ErrorCode.NOT_FOUND_ERROR, "模型不存在");
        clearModelRelationsAndEntities(id);
        // 重置计数缓存
        model.setEntityCount(0);
        model.setRelationCount(0);
        return this.updateById(model);
    }

    /**
     * 清空指定模型下的实体类型+属性 + 关系类型+属性
     */
    private void clearModelRelationsAndEntities(Long modelId) {
        // 删除关系类型+属性
        List<GraphRelationType> relationTypes = graphRelationTypeService.listByModelId(modelId);
        if (CollUtil.isNotEmpty(relationTypes)) {
            for (GraphRelationType relationType : relationTypes) {
                graphRelationTypeService.deleteRelationType(relationType.getId());
            }
        }
        // 删除实体类型+属性
        List<GraphEntityType> entityTypes = graphEntityTypeService.listByModelId(modelId);
        if (CollUtil.isNotEmpty(entityTypes)) {
            for (GraphEntityType entityType : entityTypes) {
                graphEntityTypeService.deleteEntityType(entityType.getId());
            }
        }
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public boolean copyModel(GraphModelCopyRequest request, User loginUser) {
        ThrowUtils.throwIf(request == null || request.getId() == null || request.getId() <= 0, ErrorCode.PARAMS_ERROR);
        ThrowUtils.throwIf(StrUtil.isBlank(request.getNewModelName()), ErrorCode.PARAMS_ERROR, "复制的模型名称为空");
        Long id = request.getId();
        GraphModel sourceModel = this.getById(id);
        ThrowUtils.throwIf(ObjUtil.isNull(sourceModel), ErrorCode.NOT_FOUND_ERROR, "源模型不存在");

        // 复制模型
        GraphModel newModel = new GraphModel();
        newModel.setProjectId(sourceModel.getProjectId());
        newModel.setModelName(request.getNewModelName());
        newModel.setModelDescription(sourceModel.getModelDescription());
        newModel.setVersion(ObjUtil.defaultIfNull(request.getNewVersion(), sourceModel.getVersion()));
        newModel.setEntityCount(sourceModel.getEntityCount());
        newModel.setRelationCount(sourceModel.getRelationCount());
        newModel.setCreateBy(loginUser.getId());
        boolean saved = this.save(newModel);
        ThrowUtils.throwIf(!saved, ErrorCode.OPERATION_ERROR, "复制模型失败");

        Long newModelId = newModel.getId();

        // 复制实体类型+属性
        List<GraphEntityType> entityTypes = graphEntityTypeService.listByModelId(id);
        // 旧实体类型 id -> 新实体类型 id 映射，供关系类型引用
        Map<Long, Long> entityIdMap = new java.util.HashMap<>();
        if (CollUtil.isNotEmpty(entityTypes)) {
            for (GraphEntityType src : entityTypes) {
                GraphEntityType dest = new GraphEntityType();
                BeanUtils.copyProperties(src, dest, "id", "createTime", "updateTime", "isDeleted");
                dest.setModelId(newModelId);
                boolean eSaved = graphEntityTypeService.save(dest);
                ThrowUtils.throwIf(!eSaved, ErrorCode.OPERATION_ERROR, "复制实体类型失败");
                entityIdMap.put(src.getId(), dest.getId());
                // 复制属性
                List<GraphEntityProperty> properties = graphEntityTypeService.listProperties(src.getId());
                if (CollUtil.isNotEmpty(properties)) {
                    for (GraphEntityProperty p : properties) {
                        GraphEntityProperty newP = new GraphEntityProperty();
                        BeanUtils.copyProperties(p, newP, "id", "createTime", "isDeleted");
                        newP.setEntityTypeId(dest.getId());
                        graphEntityPropertyService.save(newP);
                    }
                }
            }
        }

        // 复制关系类型+属性
        List<GraphRelationType> relationTypes = graphRelationTypeService.listByModelId(id);
        if (CollUtil.isNotEmpty(relationTypes)) {
            for (GraphRelationType src : relationTypes) {
                GraphRelationType dest = new GraphRelationType();
                BeanUtils.copyProperties(src, dest, "id", "createTime", "updateTime", "isDeleted");
                dest.setModelId(newModelId);
                dest.setSourceEntityTypeId(entityIdMap.get(src.getSourceEntityTypeId()));
                dest.setTargetEntityTypeId(entityIdMap.get(src.getTargetEntityTypeId()));
                boolean rSaved = graphRelationTypeService.save(dest);
                ThrowUtils.throwIf(!rSaved, ErrorCode.OPERATION_ERROR, "复制关系类型失败");
                // 复制关系属性
                List<GraphRelationProperty> properties = graphRelationTypeService.listProperties(src.getId());
                if (CollUtil.isNotEmpty(properties)) {
                    for (GraphRelationProperty p : properties) {
                        GraphRelationProperty newP = new GraphRelationProperty();
                        BeanUtils.copyProperties(p, newP, "id", "createTime", "isDeleted");
                        newP.setRelationTypeId(dest.getId());
                        graphRelationPropertyService.save(newP);
                    }
                }
            }
        }
        return true;
    }

    @Override
    public GraphModelVO getModelDetail(Long modelId) {
        ThrowUtils.throwIf(modelId == null || modelId <= 0, ErrorCode.PARAMS_ERROR);
        GraphModel model = this.getById(modelId);
        ThrowUtils.throwIf(ObjUtil.isNull(model), ErrorCode.NOT_FOUND_ERROR, "模型不存在");

        GraphModelVO vo = new GraphModelVO();
        BeanUtils.copyProperties(model, vo);

        // 实体类型 + 属性
        List<GraphEntityType> entityTypes = graphEntityTypeService.listByModelId(modelId);
        List<EntityTypeVO> entityTypeVOList = new ArrayList<>();
        if (CollUtil.isNotEmpty(entityTypes)) {
            // 一次性查所有实体 id -> 属性列表
            List<Long> entityTypeIds = entityTypes.stream().map(GraphEntityType::getId).collect(Collectors.toList());
            // 简化：循环查每个实体类型属性
            for (GraphEntityType entityType : entityTypes) {
                EntityTypeVO entityTypeVO = new EntityTypeVO();
                BeanUtils.copyProperties(entityType, entityTypeVO);
                entityTypeVO.setProperties(graphEntityTypeService.listProperties(entityType.getId()));
                entityTypeVOList.add(entityTypeVO);
            }
        }
        vo.setEntityTypes(entityTypeVOList);

        // 关系类型 + 属性 + 起止实体名称
        List<GraphRelationType> relationTypes = graphRelationTypeService.listByModelId(modelId);
        List<RelationTypeVO> relationTypeVOList = new ArrayList<>();
        if (CollUtil.isNotEmpty(relationTypes)) {
            // 构建 实体 id -> 名称 映射
            Map<Long, String> entityIdToName = entityTypes.stream()
                    .collect(Collectors.toMap(GraphEntityType::getId, GraphEntityType::getEntityName, (a, b) -> a));
            for (GraphRelationType relationType : relationTypes) {
                RelationTypeVO relationTypeVO = new RelationTypeVO();
                BeanUtils.copyProperties(relationType, relationTypeVO);
                relationTypeVO.setProperties(graphRelationTypeService.listProperties(relationType.getId()));
                relationTypeVO.setSourceEntityName(entityIdToName.get(relationType.getSourceEntityTypeId()));
                relationTypeVO.setTargetEntityName(entityIdToName.get(relationType.getTargetEntityTypeId()));
                relationTypeVOList.add(relationTypeVO);
            }
        }
        vo.setRelationTypes(relationTypeVOList);

        return vo;
    }

    @Override
    public void updateModelCount(Long modelId) {
        ThrowUtils.throwIf(modelId == null || modelId <= 0, ErrorCode.PARAMS_ERROR);
        GraphModel model = this.getById(modelId);
        if (ObjUtil.isNull(model)) {
            throw new BusinessException(ErrorCode.NOT_FOUND_ERROR, "模型不存在");
        }
        long entityCount = graphEntityTypeService.listByModelId(modelId).size();
        long relationCount = graphRelationTypeService.listByModelId(modelId).size();
        model.setEntityCount((int) entityCount);
        model.setRelationCount((int) relationCount);
        this.updateById(model);
    }
}
