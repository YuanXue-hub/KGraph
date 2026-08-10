<template>
  <div class="login-container">
    <div class="login-box">
      <div class="login-header">
        <svg class="login-logo" viewBox="0 0 32 32" width="56" height="56">
          <defs>
            <radialGradient id="loginKgNodeGrad" cx="35%" cy="35%">
              <stop offset="0%" stop-color="#4e5969" />
              <stop offset="100%" stop-color="#1d2129" />
            </radialGradient>
            <radialGradient id="loginKgCenterGrad" cx="35%" cy="35%">
              <stop offset="0%" stop-color="#4080ff" />
              <stop offset="100%" stop-color="#165dff" />
            </radialGradient>
          </defs>
          <g stroke="#a9aeb8" stroke-width="0.5" opacity="0.7" fill="none">
            <line x1="16" y1="16" x2="25" y2="16" />
            <line x1="16" y1="16" x2="20.5" y2="8.2" />
            <line x1="16" y1="16" x2="11.5" y2="8.2" />
            <line x1="16" y1="16" x2="7" y2="16" />
            <line x1="16" y1="16" x2="11.5" y2="23.8" />
            <line x1="16" y1="16" x2="20.5" y2="23.8" />
            <line x1="25" y1="16" x2="20.5" y2="8.2" />
            <line x1="20.5" y1="8.2" x2="11.5" y2="8.2" />
            <line x1="11.5" y1="8.2" x2="7" y2="16" />
            <line x1="7" y1="16" x2="11.5" y2="23.8" />
            <line x1="11.5" y1="23.8" x2="20.5" y2="23.8" />
            <line x1="20.5" y1="23.8" x2="25" y2="16" />
          </g>
          <g fill="url(#loginKgNodeGrad)">
            <circle cx="25" cy="16" r="1.8" />
            <circle cx="20.5" cy="8.2" r="1.8" />
            <circle cx="11.5" cy="8.2" r="1.8" />
            <circle cx="7" cy="16" r="1.8" />
            <circle cx="11.5" cy="23.8" r="1.8" />
            <circle cx="20.5" cy="23.8" r="1.8" />
          </g>
          <circle cx="16" cy="16" r="2.5" fill="url(#loginKgCenterGrad)" />
        </svg>
        <h1 class="login-title">KGraph</h1>
      </div>
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        class="login-form"
        @keyup.enter="handleLogin"
      >
        <el-form-item prop="userAccount">
          <el-input
            v-model="form.userAccount"
            placeholder="请输入账号"
            size="large"
            :prefix-icon="User"
          />
        </el-form-item>
        <el-form-item prop="userPassword">
          <el-input
            v-model="form.userPassword"
            type="password"
            placeholder="请输入密码"
            size="large"
            :prefix-icon="Lock"
            show-password
          />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="userStore.loading"
            class="login-btn"
            @click="handleLogin"
          >
            登 录
          </el-button>
        </el-form-item>
        <div class="login-footer">
          <span>还没有账号？</span>
          <el-button type="primary" link @click="openRegister">立即注册</el-button>
        </div>
      </el-form>
    </div>

    <!-- 注册弹窗 -->
    <el-dialog
      v-model="registerVisible"
      title="用户注册"
      width="440px"
      :close-on-click-modal="false"
      align-center
    >
      <el-form
        ref="registerFormRef"
        :model="registerForm"
        :rules="registerRules"
        label-width="90px"
      >
        <el-form-item label="用户名" prop="userName" required>
          <el-input v-model="registerForm.userName" placeholder="请输入用户名" maxlength="30" />
        </el-form-item>
        <el-form-item label="账号" prop="userAccount" required>
          <el-input
            v-model="registerForm.userAccount"
            placeholder="账号至少4位"
            maxlength="30"
          />
        </el-form-item>
        <el-form-item label="密码" prop="userPassword" required>
          <el-input
            v-model="registerForm.userPassword"
            type="password"
            placeholder="密码至少8位"
            show-password
          />
        </el-form-item>
        <el-form-item label="确认密码" prop="checkPassword" required>
          <el-input
            v-model="registerForm.checkPassword"
            type="password"
            placeholder="请再次输入密码"
            show-password
          />
        </el-form-item>
        <el-form-item label="个人简介" prop="userProfile">
          <el-input
            v-model="registerForm.userProfile"
            type="textarea"
            :rows="3"
            placeholder="选填，介绍一下自己"
            maxlength="200"
            show-word-limit
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="registerVisible = false">取消</el-button>
        <el-button type="primary" :loading="registerLoading" @click="handleRegister">
          注 册
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { userApi } from '@/api'

const router = useRouter()
const userStore = useUserStore()
const formRef = ref<FormInstance>()

const form = reactive({
  userAccount: '',
  userPassword: ''
})

const rules: FormRules = {
  userAccount: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  userPassword: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' }
  ]
}

async function handleLogin() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  const ok = await userStore.login(form.userAccount, form.userPassword)
  if (ok) {
    ElMessage.success('登录成功')
    router.push('/')
  } else {
    ElMessage.error('登录失败，请检查账号密码')
  }
}

/* ============ 注册逻辑 ============ */
const registerVisible = ref(false)
const registerLoading = ref(false)
const registerFormRef = ref<FormInstance>()

const registerForm = reactive({
  userName: '',
  userAccount: '',
  userPassword: '',
  checkPassword: '',
  userProfile: ''
})

const registerRules: FormRules = {
  userName: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  userAccount: [
    { required: true, message: '请输入账号', trigger: 'blur' },
    { min: 4, message: '账号至少4位', trigger: 'blur' }
  ],
  userPassword: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, message: '密码至少8位', trigger: 'blur' }
  ],
  checkPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (_rule: any, value: string, callback: any) => {
        if (value !== registerForm.userPassword) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

function openRegister() {
  registerForm.userName = ''
  registerForm.userAccount = ''
  registerForm.userPassword = ''
  registerForm.checkPassword = ''
  registerForm.userProfile = ''
  registerVisible.value = true
}

async function handleRegister() {
  if (!registerFormRef.value) return
  try {
    await registerFormRef.value.validate()
  } catch {
    return
  }
  registerLoading.value = true
  try {
    await userApi.register({
      userAccount: registerForm.userAccount,
      userPassword: registerForm.userPassword,
      checkPassword: registerForm.checkPassword,
      userName: registerForm.userName,
      userProfile: registerForm.userProfile || undefined
    })
    ElMessage.success('注册成功，请登录')
    registerVisible.value = false
    // 自动填充账号，方便登录
    form.userAccount = registerForm.userAccount
    form.userPassword = ''
  } finally {
    registerLoading.value = false
  }
}
</script>

<style scoped>
.login-container {
  height: 100vh;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.login-box {
  width: 400px;
  padding: 40px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
}

.login-header {
  text-align: center;
  margin-bottom: 30px;
}

.login-title {
  margin-top: 12px;
  font-size: 28px;
  font-weight: 700;
  color: #303133;
}

.login-logo {
  display: block;
  margin: 0 auto;
}

.login-form {
  width: 100%;
}

.login-btn {
  width: 100%;
}

.login-footer {
  display: flex;
  justify-content: center;
  align-items: center;
  font-size: 13px;
  color: #909399;
}
</style>
