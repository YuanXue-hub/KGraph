-- LLM 模型配置表（智能问答模型选择）
-- 说明：智能问答页面右下角模型选择器的数据来源，Python 端 /api/chat/llm-models 读取此表。
--          问答时按前端传入的 llmModelId 动态解析模型配置，未传或无效时回退 config.json 默认模型。
-- 注意：此表暂由手动创建/维护（后续模型管理功能规划中）；api_key 仅存服务端，接口不外泄。

CREATE TABLE IF NOT EXISTS llm_model (
    id          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    provider    VARCHAR(32)  COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '供应商: deepseek/qwen/glm',
    model_name  VARCHAR(64)  COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'API调用名',
    display_name VARCHAR(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '前端展示名',
    base_url    VARCHAR(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '供应商API地址',
    api_key     VARCHAR(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'API密钥（仅服务端使用）',
    is_reasoner TINYINT      DEFAULT 0 COMMENT '推理模型标记(思维链)',
    temperature DECIMAL(3,2) DEFAULT 0.30 COMMENT '默认温度',
    enabled     TINYINT      DEFAULT 1 COMMENT '是否启用: 0-否 1-是',
    sort_order  INT          DEFAULT 0 COMMENT '前端展示排序',
    userId      BIGINT       NULL COMMENT '所属用户ID（预留，模型管理用）',
    isDeleted   BIGINT       DEFAULT 0 COMMENT '逻辑删除: 0-未删除; 非0-已删除(存记录id，保证唯一键可共存)',
    create_time DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    -- 唯一键含 isDeleted：活跃记录(isDeleted=0)同 provider+model_name 仅一条；
    -- 已删除记录 isDeleted=记录id，允许多条同 provider+model_name 的删除记录共存
    UNIQUE KEY uk_model (provider, model_name, isDeleted)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci COMMENT ='LLM模型配置';

-- 初始数据：DeepSeek 系列（api_key 请替换为实际密钥）
INSERT INTO llm_model (provider, model_name, display_name, base_url, api_key, is_reasoner, temperature, enabled, sort_order)
VALUES
    ('deepseek', 'deepseek-chat',      'DeepSeek Chat',      'https://api.deepseek.com', 'REPLACE_ME', 0, 0.30, 1, 1),
    ('deepseek', 'deepseek-v4-pro',    'DeepSeek V4 Pro',    'https://api.deepseek.com', 'REPLACE_ME', 0, 0.30, 1, 2),
    ('deepseek', 'deepseek-v4-flash',  'DeepSeek V4 Flash',  'https://api.deepseek.com', 'REPLACE_ME', 0, 0.30, 1, 3);
