-- 会话元数据表（存放 AI 生成标题等会话级元信息）
-- 说明：Python 端 MysqlClient._ensure_tables() 在服务启动时会自动执行 CREATE TABLE IF NOT EXISTS，
-- 此脚本仅作为手动执行 / 数据库迁移 / 审核的参考副本，两者结构需保持一致。
--
-- 排序规则：必须与 chat_history 保持一致（utf8mb4_unicode_ci），
--          否则 LEFT JOIN 时会报 Illegal mix of collations 错误。

CREATE TABLE IF NOT EXISTS chat_session (
    sessionId VARCHAR(64)  CHARACTER SET utf8mb4
                           COLLATE utf8mb4_unicode_ci NOT NULL
                           PRIMARY KEY COMMENT '会话ID（与 chat_history.sessionId 对应）',
    userId    BIGINT       NOT NULL COMMENT '用户ID（隔离用，与 chat_history.userId 对齐）',
    title     VARCHAR(64)  CHARACTER SET utf8mb4
                           COLLATE utf8mb4_unicode_ci NOT NULL
                           DEFAULT '' COMMENT '会话标题：AI 生成 ≤20 中文字 或 用户手动重命名或 规则兜底',
    createdAt DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updatedAt DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                           ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
    INDEX idx_userId (userId)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='会话元数据（AI生成标题等）';

