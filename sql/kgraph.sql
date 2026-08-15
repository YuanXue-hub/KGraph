-- 切换库
use seedboot;

-- 图谱项目表
CREATE TABLE IF NOT EXISTS graph_project (
    id                      BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    projectName             VARCHAR(128) NOT NULL COMMENT '项目名称',
    projectDescription      TEXT COMMENT '项目描述',
    storageEngine           VARCHAR(32) DEFAULT 'neo4j' COMMENT '存储引擎类型',
    isConfiguredStorage     TINYINT(1) DEFAULT 0 COMMENT '是否已配置存储引擎: 0-否 1-是',
    isGraphSpaceCreated     TINYINT(1) DEFAULT 0 COMMENT '是否已创建图空间: 0-否 1-是',
    createBy                BIGINT COMMENT '创建人ID',
    createTime              DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updateTime              DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    isDeleted               TINYINT(1) DEFAULT 0 COMMENT '逻辑删除: 0-未删除 1-已删除'
) COMMENT '图谱项目表' COLLATE = utf8mb4_unicode_ci;

-- 图谱模型表（本体元数据）
CREATE TABLE IF NOT EXISTS graph_model (
    id                      BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    projectId               BIGINT NOT NULL COMMENT '所属项目ID',
    modelName               VARCHAR(128) NOT NULL COMMENT '模型名称',
    modelDescription        TEXT COMMENT '模型描述',
    version                 INT DEFAULT 1 COMMENT '版本号',
    entityCount             INT DEFAULT 0 COMMENT '实体类型数量（缓存统计）',
    relationCount           INT DEFAULT 0 COMMENT '关系类型数量（缓存统计）',
    createBy                BIGINT COMMENT '创建人ID',
    createTime              DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updateTime              DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    isDeleted               TINYINT(1) DEFAULT 0 COMMENT '逻辑删除: 0-未删除 1-已删除',
    INDEX idx_projectId (projectId)
) COMMENT '图谱模型（本体）表' COLLATE = utf8mb4_unicode_ci;

-- 实体类型表
CREATE TABLE IF NOT EXISTS graph_entity_type (
    id                      BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    modelId                 BIGINT NOT NULL COMMENT '关联模型ID',
    entityName              VARCHAR(128) NOT NULL COMMENT '实体类型名称',
    description             VARCHAR(512) COMMENT '实体描述',
    color                   VARCHAR(32) COMMENT '显示颜色',
    icon                    VARCHAR(64) COMMENT '图标',
    sortOrder               INT DEFAULT 0 COMMENT '排序',
    createTime              DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updateTime              DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    isDeleted               TINYINT(1) DEFAULT 0 COMMENT '逻辑删除: 0-未删除 1-已删除',
    INDEX idx_modelId (modelId)
) COMMENT '实体类型表' COLLATE = utf8mb4_unicode_ci;

-- 实体属性表
CREATE TABLE IF NOT EXISTS graph_entity_property (
    id                      BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    entityTypeId            BIGINT NOT NULL COMMENT '关联实体类型ID',
    propertyName            VARCHAR(128) NOT NULL COMMENT '属性名称',
    propertyType            VARCHAR(32) NOT NULL COMMENT '属性类型: string/number/date/boolean',
    isRequired              TINYINT(1) DEFAULT 0 COMMENT '是否必填: 0-否 1-是',
    defaultValue            VARCHAR(256) COMMENT '默认值',
    sortOrder               INT DEFAULT 0 COMMENT '排序',
    createTime              DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    isDeleted               TINYINT(1) DEFAULT 0 COMMENT '逻辑删除: 0-未删除 1-已删除',
    INDEX idx_entityTypeId (entityTypeId)
) COMMENT '实体属性表' COLLATE = utf8mb4_unicode_ci;

-- 关系类型表
CREATE TABLE IF NOT EXISTS graph_relation_type (
    id                      BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    modelId                 BIGINT NOT NULL COMMENT '关联模型ID',
    relationName            VARCHAR(128) NOT NULL COMMENT '关系名称',
    description             VARCHAR(512) COMMENT '关系描述',
    sourceEntityTypeId      BIGINT NOT NULL COMMENT '起始实体类型ID',
    targetEntityTypeId      BIGINT NOT NULL COMMENT '终止实体类型ID',
    sortOrder               INT DEFAULT 0 COMMENT '排序',
    createTime              DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updateTime              DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    isDeleted               TINYINT(1) DEFAULT 0 COMMENT '逻辑删除: 0-未删除 1-已删除',
    INDEX idx_modelId (modelId),
    INDEX idx_sourceEntity (sourceEntityTypeId),
    INDEX idx_targetEntity (targetEntityTypeId)
) COMMENT '关系类型表' COLLATE = utf8mb4_unicode_ci;

-- 关系属性表
CREATE TABLE IF NOT EXISTS graph_relation_property (
    id                      BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    relationTypeId          BIGINT NOT NULL COMMENT '关联关系类型ID',
    propertyName            VARCHAR(128) NOT NULL COMMENT '属性名称',
    propertyType            VARCHAR(32) NOT NULL COMMENT '属性类型: string/number/date/boolean',
    isRequired              TINYINT(1) DEFAULT 0 COMMENT '是否必填: 0-否 1-是',
    defaultValue            VARCHAR(256) COMMENT '默认值',
    sortOrder               INT DEFAULT 0 COMMENT '排序',
    createTime              DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    isDeleted               TINYINT(1) DEFAULT 0 COMMENT '逻辑删除: 0-未删除 1-已删除',
    INDEX idx_relationTypeId (relationTypeId)
) COMMENT '关系属性表' COLLATE = utf8mb4_unicode_ci;

-- 语料表
CREATE TABLE IF NOT EXISTS corpus (
    id                      BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    projectId               BIGINT NOT NULL COMMENT '所属项目ID',
    title                   VARCHAR(256) COMMENT '语料标题',
    content                 MEDIUMTEXT NOT NULL COMMENT '语料文本内容',
    source                  VARCHAR(128) COMMENT '来源: manual(文本输入)/file(文档上传)',
    filePath                VARCHAR(512) COMMENT '文件路径（MinIO URL）',
    fileType                VARCHAR(32) COMMENT '文件类型: pdf/docx',
    mineruTaskId            VARCHAR(128) COMMENT 'MinerU 任务ID',
    errorMsg                VARCHAR(512) COMMENT '解析失败原因',
    status                  TINYINT DEFAULT 0 COMMENT '0-处理中 1-已完成 2-失败',
    createBy                BIGINT COMMENT '上传人ID',
    createTime              DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updateTime              DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    isDeleted               TINYINT(1) DEFAULT 0 COMMENT '逻辑删除: 0-未删除 1-已删除',
    INDEX idx_projectId (projectId),
    INDEX idx_status (status)
) COMMENT '语料表' COLLATE = utf8mb4_unicode_ci;

-- 已有数据库迁移：为 corpus 表添加新字段
ALTER TABLE corpus ADD COLUMN IF NOT EXISTS fileType VARCHAR(32) COMMENT '文件类型: pdf/docx' AFTER filePath;
ALTER TABLE corpus ADD COLUMN IF NOT EXISTS mineruTaskId VARCHAR(128) COMMENT 'MinerU 任务ID' AFTER fileType;
ALTER TABLE corpus ADD COLUMN IF NOT EXISTS errorMsg VARCHAR(512) COMMENT '解析失败原因' AFTER mineruTaskId;
ALTER TABLE corpus MODIFY COLUMN status TINYINT DEFAULT 0 COMMENT '0-处理中 1-已完成 2-失败';
ALTER TABLE corpus MODIFY COLUMN source VARCHAR(128) COMMENT '来源: manual(文本输入)/file(文档上传)';

-- 数据迁移：旧的文本语料（source 为 manual 或空）状态统一改为"已完成"
UPDATE corpus SET source = 'manual' WHERE source IS NULL OR source NOT IN ('manual', 'file');
UPDATE corpus SET status = 1 WHERE source = 'manual' AND status = 0;

-- 抽取任务表
CREATE TABLE IF NOT EXISTS extraction_task (
    id                      BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    projectId               BIGINT NOT NULL COMMENT '项目ID',
    modelId                 BIGINT NOT NULL COMMENT '图谱模型ID',
    corpusId                BIGINT COMMENT '语料ID',
    inputText               MEDIUMTEXT COMMENT '手动输入文本',
    extractionType          VARCHAR(32) DEFAULT 'LLM' COMMENT '抽取方式: LLM/DL/KOS/STRUCTURE',
    inputConfig             TEXT COMMENT '抽取配置JSON',
    result                  MEDIUMTEXT COMMENT '抽取结果JSON',
    status                  TINYINT DEFAULT 0 COMMENT '0-排队 1-进行中 2-完成 3-失败',
    tokenConsumed           INT DEFAULT 0 COMMENT 'Token消耗',
    duration                BIGINT DEFAULT 0 COMMENT '耗时(毫秒)',
    createBy                BIGINT COMMENT '创建人ID',
    createTime              DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updateTime              DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_projectId (projectId),
    INDEX idx_modelId (modelId),
    INDEX idx_corpusId (corpusId),
    INDEX idx_status (status)
) COMMENT '抽取任务表' COLLATE = utf8mb4_unicode_ci;

-- 标注任务表（数据标注模块，单表+JSON存储实体/关系标注数据）
CREATE TABLE IF NOT EXISTS annotation_task (
    id                      BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    taskName                VARCHAR(128) NOT NULL COMMENT '标注任务名称',
    projectId               BIGINT NOT NULL COMMENT '所属项目ID',
    corpusId                BIGINT COMMENT '语料ID',
    corpusTitle             VARCHAR(256) COMMENT '语料标题',
    text                    MEDIUMTEXT COMMENT '标注原文',
    annotator               VARCHAR(64) COMMENT '标注员',
    reviewer                VARCHAR(64) COMMENT '审核员',
    totalSentences          INT DEFAULT 0 COMMENT '总句子数',
    annotatedSentences      INT DEFAULT 0 COMMENT '已标注句子数',
    entities                MEDIUMTEXT COMMENT '实体标注JSON: [{text,type,sentenceIdx,start,end}]',
    relations               MEDIUMTEXT COMMENT '关系标注JSON: [{head,headId,relation,tail,tailId}]',
    createBy                BIGINT COMMENT '创建人ID',
    createTime              DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updateTime              DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    isDeleted               TINYINT(1) DEFAULT 0 COMMENT '逻辑删除: 0-未删除 1-已删除',
    INDEX idx_projectId (projectId),
    INDEX idx_corpusId (corpusId)
) COMMENT '标注任务表' COLLATE = utf8mb4_unicode_ci;

-- 训练任务表（模型训练模块，单表+JSON存储配置/指标/历史）
CREATE TABLE IF NOT EXISTS train_task (
    id                      BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    taskName                VARCHAR(128) NOT NULL COMMENT '训练任务名称',
    projectId               BIGINT NOT NULL COMMENT '所属项目ID',
    annotationTaskId        BIGINT COMMENT '关联标注任务ID',
    dataset                 VARCHAR(256) COMMENT '训练数据集名称',
    architecture            VARCHAR(64) NOT NULL COMMENT '模型架构: BiLSTM-CRF/BERT-CRF/SPAN-BERT/BERT-RE',
    version                 VARCHAR(32) COMMENT '版本号',
    status                  VARCHAR(32) DEFAULT 'pending' COMMENT '训练状态: pending/training/done/failed',
    progress                INT DEFAULT 0 COMMENT '训练进度百分比',
    currentEpoch            INT DEFAULT 0 COMMENT '当前轮次',
    epochs                  INT DEFAULT 20 COMMENT '总轮次',
    config                  TEXT COMMENT '训练配置JSON',
    metrics                 TEXT COMMENT '训练指标JSON: {loss,precision,recall,f1}',
    history                 MEDIUMTEXT COMMENT '训练历史JSON: [{epoch,loss,precision,recall,f1}]',
    createBy                BIGINT COMMENT '创建人ID',
    createTime              DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updateTime              DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    isDeleted               TINYINT(1) DEFAULT 0 COMMENT '逻辑删除: 0-未删除 1-已删除',
    INDEX idx_projectId (projectId),
    INDEX idx_annotationTaskId (annotationTaskId),
    INDEX idx_status (status)
) COMMENT '训练任务表' COLLATE = utf8mb4_unicode_ci;
