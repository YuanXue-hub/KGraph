package com.yuan.seedboot.model.request;

import lombok.Data;

import java.io.Serializable;
import java.util.List;

/**
 * 基于 KOS 的知识抽取请求
 */
@Data
public class ExtractionKosRequest implements Serializable {

    /**
     * 项目 id
     */
    private Long projectId;

    /**
     * 图谱模型 id
     */
    private Long modelId;

    /**
     * 语料 id（可选，与 inputText 二选一）
     */
    private Long corpusId;

    /**
     * 手动输入文本（与 corpusId 二选一）
     */
    private String inputText;

    /**
     * KOS 抽取参数
     */
    private KosConfig kosConfig;

    @Data
    public static class KosConfig implements Serializable {
        /**
         * 高频术语数量（默认 10）
         */
        private Integer termCount = 10;

        /**
         * 高频概念数量（默认 10）
         */
        private Integer conceptCount = 10;

        /**
         * 范畴分类数量（默认 10）
         */
        private Integer categoryCount = 10;

        /**
         * 分类得分依据：高频术语 / 语义关联
         */
        private String scoreBasis = "高频术语";

        /**
         * 分类体系权重（默认 1）
         */
        private Double weight = 1.0;

        /**
         * 是否考虑权重：是 / 否
         */
        private String useWeight = "是";

        /**
         * 目标分类体系：PRES / CCT / CASDD / CNE / STKOS / NSTL
         */
        private List<String> targetSystems;

        /**
         * 是否多文档：是 / 否
         */
        private String multiDoc = "否";

        /**
         * 范畴分类前缀
         */
        private String categoryPrefix = "";

        /**
         * 是否返回词：是 / 否
         */
        private String returnWords = "是";

        /**
         * 实体识别类型
         */
        private List<String> entityTypes;
    }

    private static final long serialVersionUID = 1L;
}
