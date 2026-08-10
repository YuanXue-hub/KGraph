package com.yuan.seedboot.model.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import java.util.Date;

/**
 * 请求日志
 * @TableName request_log
 */
@TableName(value ="request_log")
public class RequestLog {
    /**
     * id
     */
    @TableId(type = IdType.AUTO)
    private Long id;

    /**
     * 用户id
     */
    private Long userId;

    /**
     * API Key id
     */
    private Long apiKeyId;

    /**
     * 使用的模型名称
     */
    private String modelName;

    /**
     * 输入Token数
     */
    private Integer promptTokens;

    /**
     * 输出Token数
     */
    private Integer completionTokens;

    /**
     * 总Token数
     */
    private Integer totalTokens;

    /**
     * 请求耗时（毫秒）
     */
    private Integer duration;

    /**
     * 状态：success/failed
     */
    private String status;

    /**
     * 错误信息
     */
    private String errorMessage;

    /**
     * 创建时间
     */
    private Date createTime;

    /**
     * 更新时间
     */
    private Date updateTime;

    /**
     * id
     */
    public Long getId() {
        return id;
    }

    /**
     * id
     */
    public void setId(Long id) {
        this.id = id;
    }

    /**
     * 用户id
     */
    public Long getUserId() {
        return userId;
    }

    /**
     * 用户id
     */
    public void setUserId(Long userId) {
        this.userId = userId;
    }

    /**
     * API Key id
     */
    public Long getApiKeyId() {
        return apiKeyId;
    }

    /**
     * API Key id
     */
    public void setApiKeyId(Long apiKeyId) {
        this.apiKeyId = apiKeyId;
    }

    /**
     * 使用的模型名称
     */
    public String getModelName() {
        return modelName;
    }

    /**
     * 使用的模型名称
     */
    public void setModelName(String modelName) {
        this.modelName = modelName;
    }

    /**
     * 输入Token数
     */
    public Integer getPromptTokens() {
        return promptTokens;
    }

    /**
     * 输入Token数
     */
    public void setPromptTokens(Integer promptTokens) {
        this.promptTokens = promptTokens;
    }

    /**
     * 输出Token数
     */
    public Integer getCompletionTokens() {
        return completionTokens;
    }

    /**
     * 输出Token数
     */
    public void setCompletionTokens(Integer completionTokens) {
        this.completionTokens = completionTokens;
    }

    /**
     * 总Token数
     */
    public Integer getTotalTokens() {
        return totalTokens;
    }

    /**
     * 总Token数
     */
    public void setTotalTokens(Integer totalTokens) {
        this.totalTokens = totalTokens;
    }

    /**
     * 请求耗时（毫秒）
     */
    public Integer getDuration() {
        return duration;
    }

    /**
     * 请求耗时（毫秒）
     */
    public void setDuration(Integer duration) {
        this.duration = duration;
    }

    /**
     * 状态：success/failed
     */
    public String getStatus() {
        return status;
    }

    /**
     * 状态：success/failed
     */
    public void setStatus(String status) {
        this.status = status;
    }

    /**
     * 错误信息
     */
    public String getErrorMessage() {
        return errorMessage;
    }

    /**
     * 错误信息
     */
    public void setErrorMessage(String errorMessage) {
        this.errorMessage = errorMessage;
    }

    /**
     * 创建时间
     */
    public Date getCreateTime() {
        return createTime;
    }

    /**
     * 创建时间
     */
    public void setCreateTime(Date createTime) {
        this.createTime = createTime;
    }

    /**
     * 更新时间
     */
    public Date getUpdateTime() {
        return updateTime;
    }

    /**
     * 更新时间
     */
    public void setUpdateTime(Date updateTime) {
        this.updateTime = updateTime;
    }
}