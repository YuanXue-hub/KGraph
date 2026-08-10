package com.yuan.seedboot.service.Impl;

import cn.hutool.core.collection.CollUtil;
import cn.hutool.core.util.ObjUtil;
import cn.hutool.core.util.StrUtil;
import cn.hutool.json.JSONObject;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.yuan.seedboot.common.PageRequest;
import com.yuan.seedboot.config.PythonServiceClient;
import com.yuan.seedboot.exception.BusinessException;
import com.yuan.seedboot.exception.ErrorCode;
import com.yuan.seedboot.exception.ThrowUtils;
import com.yuan.seedboot.mapper.ExtractionTaskMapper;
import com.yuan.seedboot.model.entity.*;
import com.yuan.seedboot.model.request.ExtractionDlRequest;
import com.yuan.seedboot.model.request.ExtractionKosRequest;
import com.yuan.seedboot.model.request.ExtractionRequest;
import com.yuan.seedboot.service.*;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * @description 针对表【extraction_task(抽取任务)】的数据库操作Service实现
 */
@Slf4j
@Service
public class ExtractionTaskServiceImpl extends ServiceImpl<ExtractionTaskMapper, ExtractionTask>
        implements ExtractionTaskService {

    @Resource
    private CorpusService corpusService;

    @Resource
    private GraphEntityTypeService graphEntityTypeService;

    @Resource
    private GraphRelationTypeService graphRelationTypeService;

    @Resource
    private PythonServiceClient pythonServiceClient;

    @Override
    public ExtractionTask createExtraction(ExtractionRequest request, User loginUser) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        ThrowUtils.throwIf(request.getProjectId() == null, ErrorCode.PARAMS_ERROR, "项目 id 为空");
        ThrowUtils.throwIf(request.getModelId() == null, ErrorCode.PARAMS_ERROR, "模型 id 为空");

        // 1. 获取语料文本
        String text = resolveInputText(request);

        // 2. 组装 ontology（优先使用自定义实体/关系类型，否则查模型本体）
        Map<String, Object> ontology;
        if (CollUtil.isNotEmpty(request.getCustomEntityTypes()) || CollUtil.isNotEmpty(request.getCustomRelationTypes())) {
            ontology = buildCustomOntology(request.getCustomEntityTypes(), request.getCustomRelationTypes());
        } else {
            ontology = buildOntology(request.getModelId());
        }

        // 3. 创建任务记录（初始状态：进行中）
        ExtractionTask task = new ExtractionTask();
        task.setProjectId(request.getProjectId());
        task.setModelId(request.getModelId());
        task.setCorpusId(request.getCorpusId());
        task.setInputText(request.getInputText());
        task.setExtractionType("LLM");
        task.setInputConfig(buildInputConfig(request));
        task.setStatus(1);
        task.setTokenConsumed(0);
        task.setDuration(0L);
        task.setCreateBy(loginUser.getId());
        boolean saved = this.save(task);
        ThrowUtils.throwIf(!saved, ErrorCode.OPERATION_ERROR, "创建抽取任务失败");

        // 4. 调用 Python 执行抽取
        long startTs = System.currentTimeMillis();
        try {
            String mode = StrUtil.blankToDefault(request.getMode(), "zero_shot");
            JSONObject resp = pythonServiceClient.extract(text, ontology, request.getModelId(), mode);

            // 5. 填充结果
            task.setResult(resp.toString());
            task.setStatus(2);
            task.setTokenConsumed(resp.getInt("tokenConsumed", 0));
            task.setDuration(resp.getLong("duration", 0L));
        } catch (Exception e) {
            log.error("抽取任务执行失败, taskId={}", task.getId(), e);
            task.setStatus(3);
            task.setDuration(System.currentTimeMillis() - startTs);
            this.updateById(task);
            throw e instanceof BusinessException ? (BusinessException) e
                    : new BusinessException(ErrorCode.OPERATION_ERROR, "抽取任务执行失败: " + e.getMessage());
        }
        this.updateById(task);
        return task;
    }

    @Override
    public ExtractionTask createKosExtraction(ExtractionKosRequest request, User loginUser) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        ThrowUtils.throwIf(request.getProjectId() == null, ErrorCode.PARAMS_ERROR, "项目 id 为空");
        ThrowUtils.throwIf(request.getModelId() == null, ErrorCode.PARAMS_ERROR, "模型 id 为空");

        // 1. 获取语料文本
        String text = resolveKosInputText(request);

        // 2. 组装 ontology（用于类型对齐，KOS 可选）
        Map<String, Object> ontology = buildOntology(request.getModelId());

        // 3. 创建任务记录（初始状态：进行中）
        ExtractionTask task = new ExtractionTask();
        task.setProjectId(request.getProjectId());
        task.setModelId(request.getModelId());
        task.setCorpusId(request.getCorpusId());
        task.setInputText(request.getInputText());
        task.setExtractionType("KOS");
        task.setInputConfig(buildKosInputConfig(request));
        task.setStatus(1);
        task.setTokenConsumed(0);
        task.setDuration(0L);
        task.setCreateBy(loginUser.getId());
        boolean saved = this.save(task);
        ThrowUtils.throwIf(!saved, ErrorCode.OPERATION_ERROR, "创建抽取任务失败");

        // 4. 调用 Python 执行 KOS 抽取
        long startTs = System.currentTimeMillis();
        try {
            JSONObject resp = pythonServiceClient.kosExtract(text, ontology, request.getModelId(), request.getKosConfig());

            // 5. 填充结果
            task.setResult(resp.toString());
            task.setStatus(2);
            task.setTokenConsumed(resp.getInt("tokenConsumed", 0));
            task.setDuration(resp.getLong("duration", 0L));
        } catch (Exception e) {
            log.error("KOS 抽取任务执行失败, taskId={}", task.getId(), e);
            task.setStatus(3);
            task.setDuration(System.currentTimeMillis() - startTs);
            this.updateById(task);
            throw e instanceof BusinessException ? (BusinessException) e
                    : new BusinessException(ErrorCode.OPERATION_ERROR, "KOS 抽取任务执行失败: " + e.getMessage());
        }
        this.updateById(task);
        return task;
    }

    @Override
    public ExtractionTask createDlExtraction(ExtractionDlRequest request, User loginUser) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        ThrowUtils.throwIf(request.getProjectId() == null, ErrorCode.PARAMS_ERROR, "项目 id 为空");
        ThrowUtils.throwIf(request.getModelId() == null, ErrorCode.PARAMS_ERROR, "模型 id 为空");

        // 1. 获取语料文本
        String text = resolveDlInputText(request);

        // 2. 组装 ontology（用于类型对齐）
        Map<String, Object> ontology = buildOntology(request.getModelId());

        // 3. 创建任务记录（初始状态：进行中）
        ExtractionTask task = new ExtractionTask();
        task.setProjectId(request.getProjectId());
        task.setModelId(request.getModelId());
        task.setCorpusId(request.getCorpusId());
        task.setInputText(request.getInputText());
        task.setExtractionType("DL");
        task.setInputConfig(buildDlInputConfig(request));
        task.setStatus(1);
        task.setTokenConsumed(0);
        task.setDuration(0L);
        task.setCreateBy(loginUser.getId());
        boolean saved = this.save(task);
        ThrowUtils.throwIf(!saved, ErrorCode.OPERATION_ERROR, "创建抽取任务失败");

        // 4. 调用 Python 执行深度学习抽取
        long startTs = System.currentTimeMillis();
        try {
            JSONObject resp = pythonServiceClient.dlExtract(text, ontology, request.getModelId(), request.getDlConfig());

            // 5. 填充结果
            task.setResult(resp.toString());
            task.setStatus(2);
            task.setTokenConsumed(resp.getInt("tokenConsumed", 0));
            task.setDuration(resp.getLong("duration", 0L));
        } catch (Exception e) {
            log.error("深度学习抽取任务执行失败, taskId={}", task.getId(), e);
            task.setStatus(3);
            task.setDuration(System.currentTimeMillis() - startTs);
            this.updateById(task);
            throw e instanceof BusinessException ? (BusinessException) e
                    : new BusinessException(ErrorCode.OPERATION_ERROR, "深度学习抽取任务执行失败: " + e.getMessage());
        }
        this.updateById(task);
        return task;
    }

    /**
     * 解析深度学习抽取输入文本
     */
    private String resolveDlInputText(ExtractionDlRequest request) {
        if (request.getCorpusId() != null) {
            Corpus corpus = corpusService.getById(request.getCorpusId());
            ThrowUtils.throwIf(ObjUtil.isNull(corpus), ErrorCode.NOT_FOUND_ERROR, "语料不存在");
            return corpus.getContent();
        }
        ThrowUtils.throwIf(StrUtil.isBlank(request.getInputText()), ErrorCode.PARAMS_ERROR, "输入文本为空");
        return request.getInputText();
    }

    /**
     * 构建深度学习抽取配置 JSON 字符串
     */
    private String buildDlInputConfig(ExtractionDlRequest request) {
        Map<String, Object> config = new HashMap<>();
        config.put("type", "DL");
        if (request.getDlConfig() != null) {
            config.put("dlConfig", request.getDlConfig());
        }
        return cn.hutool.json.JSONUtil.toJsonStr(config);
    }

    /**
     * 解析输入文本：优先使用 corpusId 对应的语料内容，否则使用 inputText
     */
    private String resolveInputText(ExtractionRequest request) {
        if (request.getCorpusId() != null) {
            Corpus corpus = corpusService.getById(request.getCorpusId());
            ThrowUtils.throwIf(ObjUtil.isNull(corpus), ErrorCode.NOT_FOUND_ERROR, "语料不存在");
            return corpus.getContent();
        }
        ThrowUtils.throwIf(StrUtil.isBlank(request.getInputText()), ErrorCode.PARAMS_ERROR, "输入文本为空");
        return request.getInputText();
    }

    /**
     * 解析 KOS 抽取输入文本
     */
    private String resolveKosInputText(ExtractionKosRequest request) {
        if (request.getCorpusId() != null) {
            Corpus corpus = corpusService.getById(request.getCorpusId());
            ThrowUtils.throwIf(ObjUtil.isNull(corpus), ErrorCode.NOT_FOUND_ERROR, "语料不存在");
            return corpus.getContent();
        }
        ThrowUtils.throwIf(StrUtil.isBlank(request.getInputText()), ErrorCode.PARAMS_ERROR, "输入文本为空");
        return request.getInputText();
    }

    /**
     * 构建 KOS 抽取配置 JSON 字符串
     */
    private String buildKosInputConfig(ExtractionKosRequest request) {
        Map<String, Object> config = new HashMap<>();
        config.put("type", "KOS");
        if (request.getKosConfig() != null) {
            config.put("kosConfig", request.getKosConfig());
        }
        return cn.hutool.json.JSONUtil.toJsonStr(config);
    }

    /**
     * 组装本体 JSON
     * {entities:[{name, properties:[{name,type,...]}], relations:[{name, source, target, properties:[...]}]}
     */
    private Map<String, Object> buildOntology(Long modelId) {
        Map<String, Object> ontology = new HashMap<>();
        // 实体
        List<GraphEntityType> entityTypes = graphEntityTypeService.listByModelId(modelId);
        List<Map<String, Object>> entities = new ArrayList<>();
        if (CollUtil.isNotEmpty(entityTypes)) {
            for (GraphEntityType entityType : entityTypes) {
                Map<String, Object> entity = new HashMap<>();
                entity.put("name", entityType.getEntityName());
                entity.put("description", entityType.getDescription());
                List<GraphEntityProperty> props = graphEntityTypeService.listProperties(entityType.getId());
                List<Map<String, Object>> propList = new ArrayList<>();
                if (CollUtil.isNotEmpty(props)) {
                    for (GraphEntityProperty p : props) {
                        Map<String, Object> pm = new HashMap<>();
                        pm.put("name", p.getPropertyName());
                        pm.put("type", p.getPropertyType());
                        pm.put("isRequired", p.getIsRequired());
                        propList.add(pm);
                    }
                }
                entity.put("properties", propList);
                entities.add(entity);
            }
        }
        ontology.put("entities", entities);

        // 关系
        List<GraphRelationType> relationTypes = graphRelationTypeService.listByModelId(modelId);
        // 构建 实体 id -> 名称 映射
        Map<Long, String> entityIdToName = new HashMap<>();
        if (CollUtil.isNotEmpty(entityTypes)) {
            for (GraphEntityType entityType : entityTypes) {
                entityIdToName.put(entityType.getId(), entityType.getEntityName());
            }
        }
        List<Map<String, Object>> relations = new ArrayList<>();
        if (CollUtil.isNotEmpty(relationTypes)) {
            for (GraphRelationType relationType : relationTypes) {
                Map<String, Object> relation = new HashMap<>();
                relation.put("name", relationType.getRelationName());
                relation.put("description", relationType.getDescription());
                relation.put("source", entityIdToName.get(relationType.getSourceEntityTypeId()));
                relation.put("target", entityIdToName.get(relationType.getTargetEntityTypeId()));
                List<GraphRelationProperty> props = graphRelationTypeService.listProperties(relationType.getId());
                List<Map<String, Object>> propList = new ArrayList<>();
                if (CollUtil.isNotEmpty(props)) {
                    for (GraphRelationProperty p : props) {
                        Map<String, Object> pm = new HashMap<>();
                        pm.put("name", p.getPropertyName());
                        pm.put("type", p.getPropertyType());
                        pm.put("isRequired", p.getIsRequired());
                        propList.add(pm);
                    }
                }
                relation.put("properties", propList);
                relations.add(relation);
            }
        }
        ontology.put("relations", relations);
        return ontology;
    }

    /**
     * 从自定义实体/关系类型构建本体 JSON
     */
    private Map<String, Object> buildCustomOntology(List<String> customEntityTypes, List<String> customRelationTypes) {
        Map<String, Object> ontology = new HashMap<>();
        List<Map<String, Object>> entities = new ArrayList<>();
        if (CollUtil.isNotEmpty(customEntityTypes)) {
            for (String name : customEntityTypes) {
                if (StrUtil.isBlank(name)) continue;
                Map<String, Object> entity = new HashMap<>();
                entity.put("name", name.trim());
                entity.put("properties", new ArrayList<>());
                entities.add(entity);
            }
        }
        ontology.put("entities", entities);

        List<Map<String, Object>> relations = new ArrayList<>();
        if (CollUtil.isNotEmpty(customRelationTypes)) {
            for (String name : customRelationTypes) {
                if (StrUtil.isBlank(name)) continue;
                Map<String, Object> relation = new HashMap<>();
                relation.put("name", name.trim());
                relation.put("source", "实体");
                relation.put("target", "实体");
                relation.put("properties", new ArrayList<>());
                relations.add(relation);
            }
        }
        ontology.put("relations", relations);
        return ontology;
    }

    /**
     * 构建抽取配置 JSON 字符串
     */
    private String buildInputConfig(ExtractionRequest request) {
        Map<String, Object> config = new HashMap<>();
        config.put("mode", StrUtil.blankToDefault(request.getMode(), "zero_shot"));
        return cn.hutool.json.JSONUtil.toJsonStr(config);
    }

    @Override
    public Page<ExtractionTask> listExtractionTasks(Long projectId, String extractionType, PageRequest pageRequest) {
        ThrowUtils.throwIf(pageRequest == null, ErrorCode.PARAMS_ERROR);
        long current = pageRequest.getPageNum();
        long pageSize = pageRequest.getPageSize();
        String sortField = pageRequest.getSortField();
        String sortOrder = pageRequest.getSortOrder();
        QueryWrapper<ExtractionTask> queryWrapper = new QueryWrapper<>();
        queryWrapper.eq(ObjUtil.isNotNull(projectId) && projectId > 0, "projectId", projectId);
        queryWrapper.eq(StrUtil.isNotBlank(extractionType), "extractionType", extractionType);
        queryWrapper.orderBy(StrUtil.isNotBlank(sortField), "ascend".equals(sortOrder), sortField);
        return this.page(new Page<>(current, pageSize), queryWrapper);
    }

    @Override
    public ExtractionTask getExtractionTask(Long id) {
        ThrowUtils.throwIf(id == null || id <= 0, ErrorCode.PARAMS_ERROR);
        ExtractionTask task = this.getById(id);
        ThrowUtils.throwIf(ObjUtil.isNull(task), ErrorCode.NOT_FOUND_ERROR, "抽取任务不存在");
        return task;
    }
}
