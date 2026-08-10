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
     * 来源: manual/file/api
     */
    private String source;

    private static final long serialVersionUID = 1L;
}
