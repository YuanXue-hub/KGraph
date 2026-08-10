package com.yuan.seedboot.model.request;

import lombok.Data;

import java.io.Serializable;
import java.util.List;

/**
 * （半）结构化数据抽取请求
 * 用户上传 CSV/Excel 文件后，配置字段映射，按映射规则将结构化数据写入 Neo4j
 */
@Data
public class StructureExtractionRequest implements Serializable {

    /**
     * 项目 id
     */
    private Long projectId;

    /**
     * 图谱模型 id
     */
    private Long modelId;

    /**
     * 上传文件后返回的临时文件 key
     */
    private String fileKey;

    /**
     * 实体映射配置列表
     */
    private List<EntityMapping> entityMappings;

    /**
     * 关系映射配置列表
     */
    private List<RelationMapping> relationMappings;

    /**
     * 实体映射：将源数据列映射到目标实体类型及其属性
     */
    @Data
    public static class EntityMapping implements Serializable {
        /**
         * 目标实体类型名称（来自本体 Schema）
         */
        private String entityTypeName;

        /**
         * 主键列名（源数据中用于 MERGE 去重的列，映射到实体 name）
         */
        private String nameColumn;

        /**
         * 属性映射：源列名 -> 目标属性名
         */
        private List<PropertyMapping> propertyMappings;
    }

    /**
     * 关系映射：将源数据中的头尾实体列映射到关系类型
     */
    @Data
    public static class RelationMapping implements Serializable {
        /**
         * 目标关系类型名称（来自本体 Schema）
         */
        private String relationTypeName;

        /**
         * 头实体名称列（源数据中指向头实体 name 的列）
         */
        private String headNameColumn;

        /**
         * 尾实体名称列（源数据中指向尾实体 name 的列）
         */
        private String tailNameColumn;

        /**
         * 头实体类型名称
         */
        private String headEntityTypeName;

        /**
         * 尾实体类型名称
         */
        private String tailEntityTypeName;

        /**
         * 属性映射：源列名 -> 目标属性名
         */
        private List<PropertyMapping> propertyMappings;
    }

    /**
     * 属性映射：源列名 -> 目标属性名
     */
    @Data
    public static class PropertyMapping implements Serializable {
        /**
         * 源数据列名
         */
        private String sourceColumn;

        /**
         * 目标属性名
         */
        private String targetProperty;
    }

    private static final long serialVersionUID = 1L;
}
