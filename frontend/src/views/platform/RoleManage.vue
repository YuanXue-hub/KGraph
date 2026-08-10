<template>
  <div class="page-container">
    <h2 class="page-title">角色管理</h2>

    <!-- 非管理员：无权限提示 -->
    <el-result
      v-if="!userStore.isAdmin"
      icon="warning"
      title="无权限"
      sub-title="仅管理员可访问角色管理页面"
    />

    <template v-else>
      <!-- 角色概览卡片 -->
      <div class="role-cards">
        <el-card
          v-for="role in roles"
          :key="role.code"
          shadow="hover"
          class="role-card"
          :class="{ active: selectedRole === role.code }"
          @click="selectRole(role.code)"
        >
          <div class="role-card-header">
            <div class="role-icon" :style="{ background: role.iconColor }">
              <el-icon :size="24" color="#fff">
                <component :is="role.icon" />
              </el-icon>
            </div>
            <div class="role-info">
              <div class="role-name">{{ role.name }}</div>
              <div class="role-code">编码：{{ role.code }}</div>
            </div>
          </div>

          <p class="role-desc">{{ role.description }}</p>

          <div class="role-permissions">
            <span class="perm-label">权限：</span>
            <el-tag
              v-for="perm in role.permissions"
              :key="perm"
              size="small"
              class="perm-tag"
            >
              {{ perm }}
            </el-tag>
          </div>

          <div class="role-count">
            <span class="count-label">用户数量</span>
            <span class="count-number">{{ userCount[role.code] ?? 0 }}</span>
          </div>
        </el-card>
      </div>

      <!-- 角色用户列表 -->
      <el-card shadow="never" class="user-list-card">
        <template #header>
          <div class="list-header">
            <span class="list-title">{{ selectedRoleName }} - 用户列表</span>
            <el-button size="small" :icon="Refresh" @click="loadAll">刷新</el-button>
          </div>
        </template>

        <el-table v-loading="loading" :data="currentUsers" border stripe style="width: 100%">
          <el-table-column label="头像" width="80" align="center">
            <template #default="{ row }">
              <el-avatar :size="36" :src="row.userAvatar">
                {{ (row.userName || row.userAccount || '?').charAt(0) }}
              </el-avatar>
            </template>
          </el-table-column>
          <el-table-column prop="userAccount" label="账号" width="160" />
          <el-table-column prop="userName" label="昵称" width="160" />
          <el-table-column prop="userProfile" label="简介" min-width="200" show-overflow-tooltip />
          <el-table-column label="操作" width="180" align="center" fixed="right">
            <template #default="{ row }">
              <el-button size="small" :icon="Switch" @click="handleToggleRole(row)">
                切换为{{ oppositeRoleName }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { Component } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UserFilled, User, Refresh, Switch } from '@element-plus/icons-vue'
import { userApi } from '@/api'
import { useUserStore } from '@/stores/user'

interface User {
  id: string
  userAccount: string
  userName?: string
  userAvatar?: string
  userProfile?: string
  userRole?: string
}

interface RoleConfig {
  code: 'admin' | 'user'
  name: string
  description: string
  permissions: string[]
  iconColor: string
  icon: Component
}

const userStore = useUserStore()

const roles: RoleConfig[] = [
  {
    code: 'admin',
    name: '管理员',
    description: '拥有系统全部权限，可管理用户、项目和模型',
    permissions: ['用户管理', '项目管理', '模型管理', '知识抽取', '图谱探索'],
    iconColor: '#f56c6c',
    icon: UserFilled
  },
  {
    code: 'user',
    name: '普通用户',
    description: '可使用图谱探索和知识抽取等基本功能',
    permissions: ['图谱探索', '知识抽取', '语料查看'],
    iconColor: '#409eff',
    icon: User
  }
]

const selectedRole = ref<'admin' | 'user'>('admin')
const loading = ref(false)
const adminUsers = ref<User[]>([])
const normalUsers = ref<User[]>([])

const userCount = computed(() => ({
  admin: adminUsers.value.length,
  user: normalUsers.value.length
}))

const currentUsers = computed(() =>
  selectedRole.value === 'admin' ? adminUsers.value : normalUsers.value
)

const selectedRoleName = computed(
  () => roles.find((r) => r.code === selectedRole.value)?.name || ''
)

const oppositeRoleName = computed(() => (selectedRole.value === 'admin' ? '普通用户' : '管理员'))

function selectRole(code: 'admin' | 'user') {
  selectedRole.value = code
}

async function loadAdminUsers() {
  const res = await userApi.listPage({ pageNum: 1, pageSize: 100, userRole: 'admin' })
  adminUsers.value = res.data?.records || []
}

async function loadNormalUsers() {
  const res = await userApi.listPage({ pageNum: 1, pageSize: 100, userRole: 'user' })
  normalUsers.value = res.data?.records || []
}

async function loadAll() {
  loading.value = true
  try {
    await Promise.all([loadAdminUsers(), loadNormalUsers()])
  } finally {
    loading.value = false
  }
}

async function handleToggleRole(row: User) {
  const targetRole = selectedRole.value === 'admin' ? 'user' : 'admin'
  const targetName = targetRole === 'admin' ? '管理员' : '普通用户'
  try {
    await ElMessageBox.confirm(
      `确定要将用户「${row.userName || row.userAccount}」切换为「${targetName}」吗？`,
      '切换角色',
      { type: 'warning' }
    )
    await userApi.update({
      id: row.id,
      userName: row.userName || '',
      userAvatar: row.userAvatar,
      userProfile: row.userProfile,
      userRole: targetRole
    })
    ElMessage.success('角色切换成功')
    await loadAll()
  } catch {
    // 用户取消
  }
}

onMounted(() => {
  if (userStore.isAdmin) {
    loadAll()
  }
})
</script>

<style scoped>
.role-cards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 20px;
}

.role-card {
  cursor: pointer;
  border: 2px solid var(--el-card-border-color, #ebeef5);
  transition: border-color 0.2s, background-color 0.2s;
}

.role-card.active {
  border-color: #409eff;
  background-color: #ecf5ff;
}

.role-card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.role-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.role-info {
  flex: 1;
}

.role-name {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.role-code {
  font-size: 13px;
  color: #909399;
  margin-top: 4px;
}

.role-desc {
  font-size: 14px;
  color: #606266;
  margin: 12px 0;
  line-height: 1.6;
}

.role-permissions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-bottom: 16px;
}

.perm-label {
  font-size: 13px;
  color: #909399;
}

.perm-tag {
  margin: 0;
}

.role-count {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid #ebeef5;
}

.count-label {
  font-size: 13px;
  color: #909399;
}

.count-number {
  font-size: 28px;
  font-weight: 700;
  color: #409eff;
}

.user-list-card {
  margin-top: 4px;
}

.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.list-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}
</style>
