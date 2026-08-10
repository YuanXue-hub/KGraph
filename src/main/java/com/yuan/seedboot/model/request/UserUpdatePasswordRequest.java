package com.yuan.seedboot.model.request;

import lombok.Data;

import java.io.Serializable;

/**
 * 修改密码请求
 */
@Data
public class UserUpdatePasswordRequest implements Serializable {

    /**
     * 旧密码
     */
    private String oldPassword;

    /**
     * 新密码
     */
    private String newPassword;

    private static final long serialVersionUID = 1L;
}
