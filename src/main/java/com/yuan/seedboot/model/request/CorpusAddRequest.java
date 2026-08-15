package com.yuan.seedboot.model.request;

import lombok.Data;

import java.io.Serializable;

@Data
public class CorpusAddRequest implements Serializable {

    /**
     * 项目 id
     */
    private Long projectId;

    /**
     * 语料标题
     */
    private String title;

    /**
     * 语料文本内容
     */
    private String content;

    /**
     * 来源: manual(文本输入)/file(文档上传)
     */
    private String source;

    /**
     * 文件路径（MinIO URL，文档上传时必填）
     */
    private String filePath;

    /**
     * 文件类型: pdf/docx
     */
    private String fileType;

    private static final long serialVersionUID = 1L;
}
