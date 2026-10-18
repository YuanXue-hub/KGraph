-- KGraph 数据库初始化脚本（仅表结构）
-- 共 17 张表，字符集 utf8mb4
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS=0;

-- ===== 表: annotation_task =====
DROP TABLE IF EXISTS `annotation_task`;
CREATE TABLE `annotation_task` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT 'ä¸»é”®ID',
  `taskName` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'æ ‡æ³¨ä»»åŠ¡åç§°',
  `projectId` bigint NOT NULL COMMENT 'æ‰€å±žé¡¹ç›®ID',
  `corpusId` bigint DEFAULT NULL COMMENT 'è¯­æ–™ID',
  `corpusTitle` varchar(256) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'è¯­æ–™æ ‡é¢˜',
  `text` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci COMMENT 'æ ‡æ³¨åŽŸæ–‡',
  `annotator` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'æ ‡æ³¨å‘˜',
  `reviewer` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'å®¡æ ¸å‘˜',
  `totalSentences` int DEFAULT '0' COMMENT 'æ€»å¥å­æ•°',
  `annotatedSentences` int DEFAULT '0' COMMENT 'å·²æ ‡æ³¨å¥å­æ•°',
  `entities` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci COMMENT 'å®žä½“æ ‡æ³¨JSON: [{text,type,sentenceIdx,start,end}]',
  `relations` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci COMMENT 'å…³ç³»æ ‡æ³¨JSON: [{head,headId,relation,tail,tailId}]',
  `createBy` bigint DEFAULT NULL COMMENT 'åˆ›å»ºäººID',
  `createTime` datetime DEFAULT CURRENT_TIMESTAMP COMMENT 'åˆ›å»ºæ—¶é—´',
  `updateTime` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'æ›´æ–°æ—¶é—´',
  `isDeleted` tinyint(1) DEFAULT '0' COMMENT 'é€»è¾‘åˆ é™¤: 0-æœªåˆ é™¤ 1-å·²åˆ é™¤',
  PRIMARY KEY (`id`),
  KEY `idx_projectId` (`projectId`),
  KEY `idx_corpusId` (`corpusId`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='标注任务表';

-- ===== 表: chat_history =====
DROP TABLE IF EXISTS `chat_history`;
CREATE TABLE `chat_history` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT 'id',
  `message` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `messageType` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'user/ai',
  `sessionId` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '会话id',
  `userId` bigint NOT NULL COMMENT '创建用户id',
  `createTime` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updateTime` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `isDelete` tinyint NOT NULL DEFAULT '0' COMMENT '是否删除',
  PRIMARY KEY (`id`),
  KEY `idx_sessionId` (`sessionId`),
  KEY `idx_createTime` (`createTime`),
  KEY `idx_appId_createTime` (`sessionId`,`createTime`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='对话历史表';

-- ===== 表: chat_session =====
DROP TABLE IF EXISTS `chat_session`;
CREATE TABLE `chat_session` (
  `sessionId` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '会话ID',
  `userId` bigint NOT NULL COMMENT '用户ID（隔离用）',
  `title` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT 'AI 生成或用户指定的会话标题',
  `createdAt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updatedAt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`sessionId`),
  KEY `idx_userId` (`userId`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='会话表';

-- ===== 表: corpus =====
DROP TABLE IF EXISTS `corpus`;
CREATE TABLE `corpus` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT 'ä¸»é”®ID',
  `projectId` bigint NOT NULL COMMENT 'æ‰€å±žé¡¹ç›®ID',
  `title` varchar(256) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'è¯­æ–™æ ‡é¢˜',
  `content` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'è¯­æ–™æ–‡æœ¬å†…å®¹',
  `source` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'æ¥æº: manual(æ–‡æœ¬è¾“å…¥)/file(æ–‡æ¡£ä¸Šä¼ )',
  `filePath` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'æ–‡ä»¶è·¯å¾„ï¼ˆé¢„ç•™MinIOï¼‰',
  `fileType` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'æ–‡ä»¶ç±»åž‹: pdf/docx',
  `mineruTaskId` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'MinerU ä»»åŠ¡ID',
  `errorMsg` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'è§£æžå¤±è´¥åŽŸå› ',
  `status` tinyint DEFAULT '0' COMMENT '0-å¤„ç†ä¸­ 1-å·²å®Œæˆ 2-å¤±è´¥',
  `createBy` bigint DEFAULT NULL COMMENT 'ä¸Šä¼ äººID',
  `createTime` datetime DEFAULT CURRENT_TIMESTAMP COMMENT 'åˆ›å»ºæ—¶é—´',
  `updateTime` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'æ›´æ–°æ—¶é—´',
  `isDeleted` tinyint(1) DEFAULT '0' COMMENT 'é€»è¾‘åˆ é™¤: 0-æœªåˆ é™¤ 1-å·²åˆ é™¤',
  PRIMARY KEY (`id`),
  KEY `idx_projectId` (`projectId`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='语料表';

-- ===== 表: corpus_chunk =====
DROP TABLE IF EXISTS `corpus_chunk`;
CREATE TABLE `corpus_chunk` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `corpusId` bigint NOT NULL COMMENT '所属语料ID',
  `projectId` bigint NOT NULL COMMENT '所属项目ID（冗余，便于按项目统计）',
  `chunkIndex` int NOT NULL COMMENT '块序号，从0开始',
  `content` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '块文本',
  `startOffset` int NOT NULL COMMENT '块起始偏移（闭区间，含）',
  `endOffset` int NOT NULL COMMENT '块结束偏移（闭区间，含）',
  `charCount` int NOT NULL COMMENT '块字符数',
  `strategy` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '分块策略: fixed/sentence/recursive/structure',
  `chunkSize` int DEFAULT NULL COMMENT '生成时的块大小参数（快照）',
  `overlap` int DEFAULT NULL COMMENT '生成时的重叠参数（快照）',
  `customSeparator` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '生成时的自定义分隔符（快照，仅recursive；避开保留字separator）',
  `createBy` bigint DEFAULT NULL COMMENT '操作人ID',
  `createTime` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `isDeleted` tinyint(1) DEFAULT '0' COMMENT '逻辑删除: 0-未删除 1-已删除',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_corpus_chunk` (`corpusId`,`chunkIndex`),
  KEY `idx_projectId` (`projectId`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='语料分块表';

-- ===== 表: evaluation_record =====
DROP TABLE IF EXISTS `evaluation_record`;
CREATE TABLE `evaluation_record` (
  `id` bigint NOT NULL COMMENT '雪花ID',
  `taskId` bigint NOT NULL COMMENT '评估的抽取任务ID',
  `sampleSize` int NOT NULL DEFAULT '30' COMMENT '抽样数（0=全部）',
  `overall` decimal(6,4) DEFAULT NULL COMMENT '综合得分0-1',
  `result` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci COMMENT '完整评估报告JSON',
  `tokenConsumed` int DEFAULT NULL,
  `duration` bigint DEFAULT NULL COMMENT '耗时ms',
  `isDeleted` tinyint NOT NULL DEFAULT '0' COMMENT '逻辑删除',
  `createBy` bigint DEFAULT NULL,
  `createTime` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_task` (`taskId`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='评估记录表';

-- ===== 表: extraction_task =====
DROP TABLE IF EXISTS `extraction_task`;
CREATE TABLE `extraction_task` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `projectId` bigint NOT NULL COMMENT '项目ID',
  `modelId` bigint NOT NULL COMMENT '图谱模型ID（用哪个本体抽）',
  `corpusId` bigint DEFAULT NULL COMMENT '语料ID（从哪段文本抽），NULL表示手动输入',
  `inputText` mediumtext COMMENT '手动输入文本（corpusId为空时使用）',
  `extractionType` varchar(32) DEFAULT 'LLM' COMMENT '抽取方式: LLM/DL/KOS/STRUCTURE',
  `inputConfig` text COMMENT '抽取配置JSON（模式、Prompt模板ID等）',
  `result` mediumtext COMMENT '抽取结果JSON: {entities:[], relations:[]}',
  `status` tinyint DEFAULT '0' COMMENT '0-排队 1-进行中 2-完成 3-失败',
  `tokenConsumed` int DEFAULT '0' COMMENT 'Token消耗',
  `duration` bigint DEFAULT '0' COMMENT '耗时(毫秒)',
  `createBy` bigint DEFAULT NULL COMMENT '创建人ID',
  `createTime` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updateTime` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `isDeleted` tinyint(1) DEFAULT '0' COMMENT 'é€»è¾‘åˆ é™¤: 0-æœªåˆ é™¤ 1-å·²åˆ é™¤',
  PRIMARY KEY (`id`),
  KEY `idx_projectId` (`projectId`),
  KEY `idx_modelId` (`modelId`),
  KEY `idx_corpusId` (`corpusId`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='抽取任务表';

-- ===== 表: graph_entity_property =====
DROP TABLE IF EXISTS `graph_entity_property`;
CREATE TABLE `graph_entity_property` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `entityTypeId` bigint NOT NULL COMMENT '关联实体类型ID',
  `propertyName` varchar(128) NOT NULL COMMENT '属性名称',
  `propertyType` varchar(32) NOT NULL COMMENT '属性类型: string/number/date/boolean',
  `isRequired` tinyint(1) DEFAULT '0' COMMENT '是否必填: 0-否 1-是',
  `defaultValue` varchar(256) DEFAULT NULL COMMENT '默认值',
  `description` varchar(500) DEFAULT NULL,
  `sortOrder` int DEFAULT '0' COMMENT '排序',
  `createTime` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `isDeleted` tinyint(1) DEFAULT '0' COMMENT '逻辑删除: 0-未删除 1-已删除',
  PRIMARY KEY (`id`),
  KEY `idx_entityTypeId` (`entityTypeId`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='实体属性表';

-- ===== 表: graph_entity_type =====
DROP TABLE IF EXISTS `graph_entity_type`;
CREATE TABLE `graph_entity_type` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `modelId` bigint NOT NULL COMMENT '关联模型ID',
  `entityName` varchar(128) NOT NULL COMMENT '实体类型名称',
  `description` varchar(512) DEFAULT NULL COMMENT '实体描述',
  `color` varchar(32) DEFAULT NULL COMMENT '显示颜色',
  `icon` varchar(64) DEFAULT NULL COMMENT '图标',
  `sortOrder` int DEFAULT '0' COMMENT '排序',
  `createTime` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updateTime` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `isDeleted` tinyint(1) DEFAULT '0' COMMENT '逻辑删除: 0-未删除 1-已删除',
  PRIMARY KEY (`id`),
  KEY `idx_modelId` (`modelId`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='实体类型表';

-- ===== 表: graph_model =====
DROP TABLE IF EXISTS `graph_model`;
CREATE TABLE `graph_model` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `projectId` bigint NOT NULL COMMENT '所属项目ID',
  `modelName` varchar(128) NOT NULL COMMENT '模型名称',
  `modelDescription` text COMMENT '模型描述',
  `version` int DEFAULT '1' COMMENT '版本号',
  `entityCount` int DEFAULT '0' COMMENT '实体类型数量（缓存统计）',
  `relationCount` int DEFAULT '0' COMMENT '关系类型数量（缓存统计）',
  `createBy` bigint DEFAULT NULL COMMENT '创建人ID',
  `createTime` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updateTime` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `isDeleted` tinyint(1) DEFAULT '0' COMMENT '逻辑删除: 0-未删除 1-已删除',
  PRIMARY KEY (`id`),
  KEY `idx_projectId` (`projectId`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='图谱模型表';

-- ===== 表: graph_project =====
DROP TABLE IF EXISTS `graph_project`;
CREATE TABLE `graph_project` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `projectName` varchar(128) NOT NULL COMMENT '项目名称',
  `projectDescription` text COMMENT '项目描述',
  `storageEngine` varchar(32) DEFAULT 'neo4j' COMMENT '存储引擎类型',
  `isConfiguredStorage` tinyint(1) DEFAULT '0' COMMENT '是否已配置存储引擎: 0-否 1-是',
  `isGraphSpaceCreated` tinyint(1) DEFAULT '0' COMMENT '是否已创建图空间: 0-否 1-是',
  `createBy` bigint DEFAULT NULL COMMENT '创建人ID',
  `createTime` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updateTime` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `isDeleted` tinyint(1) DEFAULT '0' COMMENT '逻辑删除: 0-未删除 1-已删除',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='图谱项目表';

-- ===== 表: graph_relation_property =====
DROP TABLE IF EXISTS `graph_relation_property`;
CREATE TABLE `graph_relation_property` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `relationTypeId` bigint NOT NULL COMMENT '关联关系类型ID',
  `propertyName` varchar(128) NOT NULL COMMENT '属性名称',
  `propertyType` varchar(32) NOT NULL COMMENT '属性类型: string/number/date/boolean',
  `isRequired` tinyint(1) DEFAULT '0' COMMENT '是否必填: 0-否 1-是',
  `defaultValue` varchar(256) DEFAULT NULL COMMENT '默认值',
  `description` varchar(500) DEFAULT NULL,
  `sortOrder` int DEFAULT '0' COMMENT '排序',
  `createTime` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `isDeleted` tinyint(1) DEFAULT '0' COMMENT '逻辑删除: 0-未删除 1-已删除',
  PRIMARY KEY (`id`),
  KEY `idx_relationTypeId` (`relationTypeId`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='关系属性表';

-- ===== 表: graph_relation_type =====
DROP TABLE IF EXISTS `graph_relation_type`;
CREATE TABLE `graph_relation_type` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `modelId` bigint NOT NULL COMMENT '关联模型ID',
  `relationName` varchar(128) NOT NULL COMMENT '关系名称',
  `description` varchar(512) DEFAULT NULL COMMENT '关系描述',
  `sourceEntityTypeId` bigint NOT NULL COMMENT '起始实体类型ID',
  `targetEntityTypeId` bigint NOT NULL COMMENT '终止实体类型ID',
  `sortOrder` int DEFAULT '0' COMMENT '排序',
  `createTime` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updateTime` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `isDeleted` tinyint(1) DEFAULT '0' COMMENT '逻辑删除: 0-未删除 1-已删除',
  PRIMARY KEY (`id`),
  KEY `idx_modelId` (`modelId`),
  KEY `idx_sourceEntity` (`sourceEntityTypeId`),
  KEY `idx_targetEntity` (`targetEntityTypeId`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='关系类型表';

-- ===== 表: llm_model =====
DROP TABLE IF EXISTS `llm_model`;
CREATE TABLE `llm_model` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `provider` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '供应商: deepseek/qwen/glm',
  `model_name` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'API调用名',
  `display_name` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '前端展示名',
  `base_url` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '供应商API地址',
  `api_key` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `is_reasoner` tinyint DEFAULT '0' COMMENT '推理模型标记(思维链)',
  `temperature` decimal(3,2) DEFAULT '0.30',
  `enabled` tinyint DEFAULT '1',
  `sort_order` int DEFAULT '0',
  `userId` bigint DEFAULT NULL COMMENT 'æ‰€å±žç”¨æˆ·IDï¼ˆé¢„ç•™ï¼Œæ¨¡åž‹ç®¡ç†ç”¨ï¼‰',
  `isDeleted` bigint DEFAULT '0',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP,
  `update_time` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `context_window` int DEFAULT NULL COMMENT 'ä¸Šä¸‹æ–‡çª—å£(tokens)ï¼ŒNULLåˆ™æŒ‰ä¾›åº”å•†é»˜è®¤',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_model` (`provider`,`model_name`,`isDeleted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='LLM模型表';

-- ===== 表: request_log =====
DROP TABLE IF EXISTS `request_log`;
CREATE TABLE `request_log` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT 'id',
  `userId` bigint DEFAULT NULL COMMENT '用户id',
  `apiKeyId` bigint DEFAULT NULL COMMENT 'API Key id',
  `modelName` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '使用的模型名称',
  `promptTokens` int NOT NULL DEFAULT '0' COMMENT '输入Token数',
  `completionTokens` int NOT NULL DEFAULT '0' COMMENT '输出Token数',
  `totalTokens` int NOT NULL DEFAULT '0' COMMENT '总Token数',
  `duration` int NOT NULL DEFAULT '0' COMMENT '请求耗时（毫秒）',
  `status` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'success' COMMENT '状态：success/failed',
  `errorMessage` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci COMMENT '错误信息',
  `createTime` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updateTime` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_userId` (`userId`),
  KEY `idx_apiKeyId` (`apiKeyId`),
  KEY `idx_createTime` (`createTime`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='请求日志表';

-- ===== 表: train_task =====
DROP TABLE IF EXISTS `train_task`;
CREATE TABLE `train_task` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT 'ä¸»é”®ID',
  `taskName` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'è®­ç»ƒä»»åŠ¡åç§°',
  `projectId` bigint NOT NULL COMMENT 'æ‰€å±žé¡¹ç›®ID',
  `annotationTaskId` bigint DEFAULT NULL COMMENT 'å…³è”æ ‡æ³¨ä»»åŠ¡ID',
  `dataset` varchar(256) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'è®­ç»ƒæ•°æ®é›†åç§°',
  `architecture` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'æ¨¡åž‹æž¶æž„: BiLSTM-CRF/BERT-CRF/SPAN-BERT/BERT-RE',
  `version` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'ç‰ˆæœ¬å·',
  `status` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT 'pending' COMMENT 'è®­ç»ƒçŠ¶æ€: pending/training/done/failed',
  `progress` int DEFAULT '0' COMMENT 'è®­ç»ƒè¿›åº¦ç™¾åˆ†æ¯”',
  `currentEpoch` int DEFAULT '0' COMMENT 'å½“å‰è½®æ¬¡',
  `epochs` int DEFAULT '20' COMMENT 'æ€»è½®æ¬¡',
  `config` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci COMMENT 'è®­ç»ƒé…ç½®JSON',
  `metrics` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci COMMENT 'è®­ç»ƒæŒ‡æ ‡JSON: {loss,precision,recall,f1}',
  `history` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci COMMENT 'è®­ç»ƒåŽ†å²JSON: [{epoch,loss,precision,recall,f1}]',
  `createBy` bigint DEFAULT NULL COMMENT 'åˆ›å»ºäººID',
  `createTime` datetime DEFAULT CURRENT_TIMESTAMP COMMENT 'åˆ›å»ºæ—¶é—´',
  `updateTime` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'æ›´æ–°æ—¶é—´',
  `isDeleted` tinyint(1) DEFAULT '0' COMMENT 'é€»è¾‘åˆ é™¤: 0-æœªåˆ é™¤ 1-å·²åˆ é™¤',
  PRIMARY KEY (`id`),
  KEY `idx_projectId` (`projectId`),
  KEY `idx_annotationTaskId` (`annotationTaskId`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='训练任务表';

-- ===== 表: user =====
DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT 'id',
  `userAccount` varchar(256) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '账号',
  `userPassword` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '密码',
  `userName` varchar(256) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '用户昵称',
  `userAvatar` varchar(1024) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '用户头像',
  `userProfile` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '用户简介',
  `userRole` varchar(256) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'user' COMMENT '用户角色：user/admin',
  `editTime` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '编辑时间',
  `createTime` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updateTime` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `isDelete` tinyint NOT NULL DEFAULT '0' COMMENT '是否删除',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_userAccount` (`userAccount`),
  KEY `idx_userName` (`userName`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

SET FOREIGN_KEY_CHECKS=1;