package com.yuan.seedboot.service;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.yuan.seedboot.model.entity.User;
import com.baomidou.mybatisplus.extension.service.IService;
import com.yuan.seedboot.model.request.UserQueryRequest;
import com.yuan.seedboot.model.vo.LoginUserVO;
import com.yuan.seedboot.model.vo.UserVO;
import jakarta.servlet.http.HttpServletRequest;

import java.util.List;

/**
* @author Yuan
* @description 针对表【user(用户)】的数据库操作Service
* @createDate 2026-06-15 20:31:44
*/
public interface UserService extends IService<User> {

    /**
     * 用户注册（基础）
     *
     * @param userAccount   用户账户
     * @param userPassword  用户密码
     * @param checkPassword 校验密码
     * @return 新用户 id
     */
    long userRegister(String userAccount, String userPassword, String checkPassword);

    /**
     * 用户注册（含完整字段）
     *
     * @param userAccount    账号（必填）
     * @param userPassword   密码（必填）
     * @param checkPassword  确认密码（必填）
     * @param userName       昵称（必填）
     * @param userAvatar     头像（选填）
     * @param userProfile    简介（选填）
     * @return 新用户 id
     */
    long userRegister(String userAccount, String userPassword, String checkPassword,
                      String userName, String userAvatar, String userProfile);

    /**
     * 修改当前登录用户密码
     *
     * @param oldPassword 旧密码
     * @param newPassword 新密码
     * @param request     请求
     * @return 是否成功
     */
    boolean updatePassword(String oldPassword, String newPassword, HttpServletRequest request);

    /**
     * 用户登录
     *
     * @param userAccount  用户账户
     * @param userPassword 用户密码
     * @param request
     * @return 脱敏后的用户信息
     */
    LoginUserVO userLogin(String userAccount, String userPassword, HttpServletRequest request);

    /**
     * 获取当前登录用户
     *
     * @param request
     * @return
     */
    User getLoginUser(HttpServletRequest request);

    /**
     * 获取脱敏的已登录用户信息
     *
     * @return
     */
    LoginUserVO getLoginUserVO(User user);

    /**
     * 用户注销
     *
     * @param request
     * @return
     */
    boolean userLogout(HttpServletRequest request);

    UserVO getUserVO(User user);

    List<UserVO> getUserVOList(List<User> userList);

    String getEncryptPassword(String userPassword);

    QueryWrapper<User> getQueryWrapper(UserQueryRequest userQueryRequest);
}
