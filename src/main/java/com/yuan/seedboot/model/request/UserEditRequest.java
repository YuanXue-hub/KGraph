package com.yuan.seedboot.model.request;

import lombok.Data;

import java.io.Serializable;

/**
 * 用户编辑个人信息请求（仅允许修改昵称、头像、简介，不可改角色）
 */
@Data
public class UserEditRequest implements Serializable {

    /**
     * 用户昵称
     */
    private String userName;

    /**
     * 用户头像
     */
    private String userAvatar;

    /**
     * 简介
     */
    private String userProfile;

    private static final long serialVersionUID = 1L;
}
