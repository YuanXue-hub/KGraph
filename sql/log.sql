-- 请求日志表（用于记录每次请求和Token消耗）
create table if not exists request_log
(
    id              bigint auto_increment comment 'id' primary key,
    userId          bigint                                 null comment '用户id',
    apiKeyId        bigint                                 null comment 'API Key id',
    modelName       varchar(128)                           not null comment '使用的模型名称',
    promptTokens    int          default 0                 not null comment '输入Token数',
    completionTokens int         default 0                 not null comment '输出Token数',
    totalTokens     int          default 0                 not null comment '总Token数',
    duration        int          default 0                 not null comment '请求耗时（毫秒）',
    status          varchar(32)  default 'success'         not null comment '状态：success/failed',
    errorMessage    text                                   null comment '错误信息',
    createTime      datetime     default CURRENT_TIMESTAMP not null comment '创建时间',
    updateTime      datetime     default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '更新时间',
    INDEX idx_userId (userId),
    INDEX idx_apiKeyId (apiKeyId),
    INDEX idx_createTime (createTime)
    ) comment '请求日志' collate = utf8mb4_unicode_ci;