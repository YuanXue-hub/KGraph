<template>
  <div class="page-container profile-page">
    <!-- 内容区 -->
    <div class="kg-card user-card">
      <div class="user-card-banner">
        <div class="user-avatar-wrap">
          <el-avatar :size="96" :src="userInfo?.userAvatar" class="user-avatar">
            {{ avatarText }}
          </el-avatar>
        </div>
        <div class="user-info">
          <div class="user-name-row">
            <h1 class="user-name">{{ userInfo?.userName || '未设置昵称' }}</h1>
            <span class="role-badge" :class="userInfo?.userRole === 'admin' ? 'is-admin' : 'is-user'">
              {{ roleText }}
            </span>
          </div>
          <p class="user-account">@{{ userInfo?.userAccount }}</p>
          <p class="user-profile">
            {{ userInfo?.userProfile || '这个人很懒，什么都没留下' }}
          </p>
        </div>
      </div>

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

    <!-- 基本信息 -->
    <div class="kg-card form-section">
      <div class="section-head">
        <div class="section-title">
          <el-icon class="section-icon"><User /></el-icon>
          <span>基本信息</span>
        </div>
        <span class="section-subtitle">设置你的公开身份信息</span>
      </div>
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
              <div class="avatar-uploader-tip">点击上传</div>
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
    </div>

    <!-- 安全设置 -->
    <div class="kg-card form-section">
      <div class="section-head">
        <div class="section-title">
          <el-icon class="section-icon"><Lock /></el-icon>
          <span>安全设置</span>
        </div>
        <span class="section-subtitle">定期修改密码以保障账户安全</span>
      </div>
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
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules, type UploadRequestOptions } from 'element-plus'
import { Plus, User, Lock } from '@element-plus/icons-vue'
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
  max-width: 920px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
}

.page-head-left {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.page-subtitle {
  font-size: 13px;
  color: var(--text-3);
  font-weight: 400;
}

/* 顶部用户卡片 */
.user-card {
  padding: 0;
  overflow: hidden;
}

.user-card:hover {
  box-shadow: var(--shadow-1);
}

.user-card-banner {
  display: flex;
  align-items: center;
  gap: 28px;
  padding: 32px;
  background: linear-gradient(135deg, #e8f3ff 0%, #eef0ff 55%, #f0eaff 100%);
}

.user-avatar-wrap {
  flex-shrink: 0;
}

.user-avatar {
  width: 96px;
  height: 96px;
  font-size: 36px;
  font-weight: 600;
  background: linear-gradient(135deg, #165dff 0%, #6366f1 100%);
  color: #fff;
  border: 4px solid #fff;
  box-shadow: 0 6px 18px rgba(22, 93, 255, 0.22);
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
  font-size: 24px;
  font-weight: 700;
  color: var(--text-1);
  line-height: 1.2;
}

.role-badge {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.role-badge.is-admin {
  background: rgba(245, 63, 63, 0.1);
  color: #f53f3f;
}

.role-badge.is-user {
  background: rgba(22, 93, 255, 0.1);
  color: #165dff;
}

.user-account {
  margin-top: 6px;
  font-size: 13px;
  color: var(--text-3);
}

.user-profile {
  margin-top: 10px;
  font-size: 14px;
  color: var(--text-2);
  line-height: 1.6;
  word-break: break-all;
}

/* 统计数据行 */
.user-stats {
  display: flex;
  align-items: center;
  padding: 18px 32px;
  background: #fff;
  border-top: 1px solid var(--border-2);
}

.stat-item {
  flex: 1;
  text-align: center;
}

.stat-value {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-1);
  line-height: 1.4;
  word-break: break-all;
}

.stat-id {
  font-size: 13px;
  color: var(--text-3);
  font-weight: 500;
  font-family: 'SF Mono', Menlo, Consolas, monospace;
}

.stat-label {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-3);
}

.stat-divider {
  width: 1px;
  height: 32px;
  background: var(--border-1);
  margin: 0 12px;
}

/* 表单分组卡片 */
.form-section {
  padding: 0;
  overflow: hidden;
}

.form-section:hover {
  box-shadow: var(--shadow-1);
}

.section-head {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 18px 24px;
  border-bottom: 1px solid var(--border-2);
  background: #fbfcfd;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-1);
}

.section-icon {
  font-size: 17px;
  color: var(--brand-primary);
}

.section-subtitle {
  font-size: 12px;
  color: var(--text-3);
  padding-left: 25px;
}

.edit-form {
  padding: 24px;
  max-width: 560px;
}

/* 头像上传 */
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
  background: linear-gradient(135deg, #e8f3ff 0%, #eef0ff 100%);
  color: var(--brand-primary);
  border: 1px dashed var(--border-1);
  transition: all var(--t-fast);
}

.avatar-uploader:hover .avatar-preview {
  border-color: var(--brand-primary);
  background: linear-gradient(135deg, #165dff 0%, #6366f1 100%);
  color: #fff;
}

.avatar-uploader-tip {
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-3);
}

.avatar-url-input {
  flex: 1;
}
</style>
