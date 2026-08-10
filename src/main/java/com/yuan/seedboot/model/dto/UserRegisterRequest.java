package com.yuan.seedboot.model.dto;

import lombok.Data;

import java.io.Serializable;

@Data
public class UserRegisterRequest implements Serializable {

    private static final long serialVersionUID = 3191241716373120793L;

    /**
     * 账号（必填）
     */
    private String userAccount;

    /**
     * 密码（必填）
     */
    private String userPassword;

    /**
     * 确认密码（必填）
     */
    private String checkPassword;

    /**
     * 用户昵称（必填）
     */
    private String userName;

    /**
     * 用户头像 URL（选填）
     */
    private String userAvatar;

    /**
     * 个人简介（选填）
     */
    private String userProfile;
}
