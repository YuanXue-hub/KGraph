<template>
  <div class="profile-page">
    <!-- 顶部用户卡片（参考 codefather 风格） -->
    <div class="user-card">
      <div class="user-card-inner">
        <!-- 左侧头像 -->
        <div class="user-avatar-wrap">
          <el-avatar :size="120" :src="userInfo?.userAvatar" class="user-avatar">
            {{ avatarText }}
          </el-avatar>
          <el-tag :type="roleTagType" size="small" effect="dark" round class="role-badge">
            {{ roleText }}
          </el-tag>
        </div>
        <!-- 中间信息 -->
        <div class="user-info">
          <div class="user-name-row">
            <h1 class="user-name">{{ userInfo?.userName || '未设置昵称' }}</h1>
            <el-tag type="info" size="small" round class="account-tag">
              @{{ userInfo?.userAccount }}
            </el-tag>
          </div>
          <p class="user-profile">
            {{ userInfo?.userProfile || '这个人很懒，什么都没留下' }}
          </p>
        </div>
      </div>
      <!-- 统计数据行 -->
      <div class="user-stats">
        <div class="stat-item">
          <div class="stat-value">{{ formatTime(userInfo?.createTime) }}</div>
          <div class="stat-label">注册时间</div>
        </div>
        <div class="stat-divider"></div>
        <div class="stat-item">
          <div class="stat-value stat-id">{{ userInfo?.id }}</div>
          <div class="stat-label">账号 ID</div>
        </div>
        <div class="stat-divider"></div>
        <div class="stat-item">
          <div class="stat-value">{{ roleText }}</div>
          <div class="stat-label">用户角色</div>
        </div>
      </div>
    </div>

    <!-- 下方 Tab 区（编辑资料 / 修改密码） -->
    <el-card class="edit-card" shadow="never">
      <el-tabs v-model="activeTab" class="edit-tabs">
        <!-- 编辑资料 -->
        <el-tab-pane label="编辑资料" name="profile">
          <el-form
            ref="formRef"
            :model="form"
            :rules="rules"
            label-width="90px"
            class="edit-form"
          >
            <el-form-item label="用户昵称" prop="userName">
              <el-input v-model="form.userName" placeholder="请输入用户昵称" maxlength="30" />
            </el-form-item>
            <el-form-item label="头像" prop="userAvatar">
              <div class="avatar-uploader-wrap">
                <el-upload
                  class="avatar-uploader"
                  :show-file-list="false"
                  :before-upload="beforeAvatarUpload"
                  :http-request="handleAvatarUpload"
                  accept="image/*"
                >
                  <el-avatar :size="80" :src="form.userAvatar" class="avatar-preview">
                    <el-icon><Plus /></el-icon>
                  </el-avatar>
                  <div class="avatar-uploader-tip">点击上传头像</div>
                </el-upload>
                <el-input
                  v-model="form.userAvatar"
                  placeholder="也可直接输入图片 URL"
                  class="avatar-url-input"
                />
              </div>
            </el-form-item>
            <el-form-item label="个人简介" prop="userProfile">
              <el-input
                v-model="form.userProfile"
                type="textarea"
                :rows="4"
                placeholder="介绍一下自己吧"
                maxlength="200"
                show-word-limit
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="submitting" @click="handleSave">保存</el-button>
              <el-button @click="handleReset">重置</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 修改密码 -->
        <el-tab-pane label="修改密码" name="password">
          <el-form
            ref="pwdFormRef"
            :model="pwdForm"
            :rules="pwdRules"
            label-width="100px"
            class="edit-form"
          >
            <el-form-item label="旧密码" prop="oldPassword">
              <el-input
                v-model="pwdForm.oldPassword"
                type="password"
                placeholder="请输入旧密码"
                show-password
              />
            </el-form-item>
            <el-form-item label="新密码" prop="newPassword">
              <el-input
                v-model="pwdForm.newPassword"
                type="password"
                placeholder="至少8位"
                show-password
              />
            </el-form-item>
            <el-form-item label="确认新密码" prop="confirmPassword">
              <el-input
                v-model="pwdForm.confirmPassword"
                type="password"
                placeholder="请再次输入新密码"
                show-password
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="pwdSubmitting" @click="handleChangePassword">
                修改密码
              </el-button>
              <el-button @click="handlePwdReset">重置</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules, type UploadRequestOptions } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { userApi, fileApi } from '@/api'
import { useUserStore } from '@/stores/user'

interface LoginUserInfo {
  id: number
  userAccount: string
  userName?: string
  userAvatar?: string
  userProfile?: string
  userRole?: string
  createTime?: string
  updateTime?: string
}

const userStore = useUserStore()
const userInfo = computed<LoginUserInfo | null>(
  () => userStore.userInfo as LoginUserInfo | null
)

const formRef = ref<FormInstance>()
const submitting = ref(false)
const activeTab = ref('profile')

const form = ref({
  userName: '',
  userAvatar: '',
  userProfile: ''
})

const originalForm = ref({
  userName: '',
  userAvatar: '',
  userProfile: ''
})

const rules: FormRules = {
  userName: [{ required: true, message: '请输入用户昵称', trigger: 'blur' }]
}

const avatarText = computed(() => {
  const name = userInfo.value?.userName || userInfo.value?.userAccount || ''
  return name ? name.charAt(0).toUpperCase() : '?'
})

const roleTagType = computed(() => {
  return userInfo.value?.userRole === 'admin' ? 'danger' : 'primary'
})

const roleText = computed(() => {
  return userInfo.value?.userRole === 'admin' ? '管理员' : '普通用户'
})

function fillForm() {
  const u = userInfo.value
  form.value = {
    userName: u?.userName || '',
    userAvatar: u?.userAvatar || '',
    userProfile: u?.userProfile || ''
  }
  originalForm.value = { ...form.value }
}

function handleReset() {
  form.value = { ...originalForm.value }
  formRef.value?.clearValidate()
}

async function handleSave() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  submitting.value = true
  try {
    await userApi.updateMy({
      userName: form.value.userName,
      userAvatar: form.value.userAvatar,
      userProfile: form.value.userProfile
    })
    ElMessage.success('保存成功')
    await userStore.fetchCurrentUser()
    fillForm()
  } finally {
    submitting.value = false
  }
}

/* ============ 头像上传（MinIO） ============ */
function beforeAvatarUpload(file: File): boolean {
  const isImage = file.type.startsWith('image/')
  const isLt2M = file.size / 1024 / 1024 < 2
  if (!isImage) {
    ElMessage.error('头像必须是图片格式')
    return false
  }
  if (!isLt2M) {
    ElMessage.error('头像图片大小不能超过 2MB')
    return false
  }
  return true
}

async function handleAvatarUpload(options: UploadRequestOptions): Promise<void> {
  const file = options.file as File
  try {
    const res = await fileApi.uploadAvatar(file)
    if (res.code === 0 && res.data) {
      form.value.userAvatar = res.data as string
      ElMessage.success('头像上传成功，点击保存生效')
    }
  } catch {
    // 错误已由请求拦截器提示
  }
}

/* ============ 修改密码 ============ */
const pwdFormRef = ref<FormInstance>()
const pwdSubmitting = ref(false)

const pwdForm = ref({
  oldPassword: '',
  newPassword: '',
  confirmPassword: ''
})

const pwdRules: FormRules = {
  oldPassword: [{ required: true, message: '请输入旧密码', trigger: 'blur' }],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 8, message: '密码至少8位', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (_rule: any, value: string, callback: any) => {
        if (value !== pwdForm.value.newPassword) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

function handlePwdReset() {
  pwdForm.value = { oldPassword: '', newPassword: '', confirmPassword: '' }
  pwdFormRef.value?.clearValidate()
}

async function handleChangePassword() {
  if (!pwdFormRef.value) return
  try {
    await pwdFormRef.value.validate()
  } catch {
    return
  }
  pwdSubmitting.value = true
  try {
    await userApi.updatePassword({
      oldPassword: pwdForm.value.oldPassword,
      newPassword: pwdForm.value.newPassword
    })
    ElMessage.success('密码修改成功')
    handlePwdReset()
  } finally {
    pwdSubmitting.value = false
  }
}

function formatTime(t?: string): string {
  if (!t) return '-'
  return t.replace('T', ' ').substring(0, 16)
}

onMounted(async () => {
  if (!userStore.userInfo) {
    await userStore.fetchCurrentUser()
  }
  fillForm()
})
</script>

<style scoped>
.profile-page {
  max-width: 900px;
  margin: 0 auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* 顶部用户卡片 */
.user-card {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  overflow: hidden;
}

.user-card-inner {
  display: flex;
  align-items: center;
  gap: 28px;
  padding: 32px 32px 20px;
  background: linear-gradient(135deg, #f0f5ff 0%, #e6fffb 100%);
}

.user-avatar-wrap {
  position: relative;
  flex-shrink: 0;
}

.user-avatar {
  width: 120px;
  height: 120px;
  font-size: 48px;
  font-weight: 600;
  background: linear-gradient(135deg, #409eff, #67c23a);
  color: #fff;
  border: 4px solid #fff;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.role-badge {
  position: absolute;
  bottom: -6px;
  left: 50%;
  transform: translateX(-50%);
  white-space: nowrap;
}

.user-info {
  flex: 1;
  min-width: 0;
}

.user-name-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.user-name {
  margin: 0;
  font-size: 26px;
  font-weight: 700;
  color: #1d2129;
  line-height: 1.2;
}

.account-tag {
  font-size: 13px;
}

.user-profile {
  margin-top: 10px;
  font-size: 14px;
  color: #4e5969;
  line-height: 1.6;
  word-break: break-all;
}

/* 统计数据行 */
.user-stats {
  display: flex;
  align-items: center;
  padding: 16px 32px;
  background: #fff;
  border-top: 1px solid #f0f2f5;
}

.stat-item {
  flex: 1;
  text-align: center;
}

.stat-value {
  font-size: 16px;
  font-weight: 600;
  color: #1d2129;
  line-height: 1.4;
  word-break: break-all;
}

.stat-id {
  font-size: 13px;
  color: #86909c;
  font-weight: 500;
  font-family: monospace;
}

.stat-label {
  margin-top: 2px;
  font-size: 12px;
  color: #86909c;
}

.stat-divider {
  width: 1px;
  height: 28px;
  background: #e5e6eb;
  margin: 0 8px;
}

/* 下方编辑卡片 */
.edit-card {
  border-radius: 12px;
}

.edit-tabs :deep(.el-tabs__header) {
  margin-bottom: 24px;
}

.edit-tabs :deep(.el-tabs__nav-wrap::after) {
  height: 1px;
}

.edit-tabs :deep(.el-tabs__item) {
  font-size: 15px;
  height: 44px;
  line-height: 44px;
}

.edit-form {
  max-width: 540px;
  padding: 8px 0 16px;
}

.avatar-uploader-wrap {
  display: flex;
  align-items: center;
  gap: 16px;
  width: 100%;
}

.avatar-uploader {
  display: flex;
  flex-direction: column;
  align-items: center;
  cursor: pointer;
}

.avatar-uploader :deep(.el-upload) {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.avatar-preview {
  background: linear-gradient(135deg, #409eff, #67c23a);
  color: #fff;
  border: 1px dashed #dcdfe6;
}

.avatar-uploader-tip {
  margin-top: 6px;
  font-size: 12px;
  color: #909399;
}

.avatar-url-input {
  flex: 1;
}
</style>
