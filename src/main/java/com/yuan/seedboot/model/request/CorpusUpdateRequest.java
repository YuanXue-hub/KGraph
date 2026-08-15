package com.yuan.seedboot.model.request;

import lombok.Data;

import java.io.Serializable;

@Data
public class CorpusUpdateRequest implements Serializable {

    /**
     * 语料 id
     */
    private Long id;

    /**
     * 语料标题
     */
    private String title;

    /**
     * 语料文本内容
     */
    private String content;

    /**
     * 来源: manual/file
     */
    private String source;

    private static final long serialVersionUID = 1L;
}
