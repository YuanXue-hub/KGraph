<template>
  <div class="page-container">
    <!-- 工具栏 -->
    <div v-if="!userStore.isAdmin" class="kg-card">
      <div class="empty-state">
        <el-icon :size="44" color="#c9cdd4"><Lock /></el-icon>
        <p class="empty-title">无权限访问</p>
        <p class="empty-desc">仅管理员可访问角色管理页面</p>
      </div>
    </div>

    <template v-else>
      <!-- 角色概览卡片 -->
      <div class="role-cards">
        <div
          v-for="role in roles"
          :key="role.code"
          class="role-card"
          :class="{ active: selectedRole === role.code }"
          @click="selectRole(role.code)"
        >
          <div class="role-card-top">
            <div class="role-icon-wrap" :style="{ background: `linear-gradient(135deg, ${role.iconColor} 0%, ${role.iconColor}cc 100%)` }">
              <el-icon :size="22" color="#fff">
                <component :is="role.icon" />
              </el-icon>
            </div>
            <div class="role-meta">
              <div class="role-name">{{ role.name }}</div>
              <div class="role-code">{{ role.code }}</div>
            </div>
            <div class="role-count-badge">
              <span class="count-num">{{ userCount[role.code] ?? 0 }}</span>
              <span class="count-text">用户</span>
            </div>
          </div>

          <p class="role-desc">{{ role.description }}</p>

          <div class="role-perms">
            <span class="perms-label">权限</span>
            <el-tag
              v-for="perm in role.permissions"
              :key="perm"
              size="small"
              effect="plain"
              class="perm-chip"
            >
              {{ perm }}
            </el-tag>
          </div>
        </div>
      </div>

      <!-- 角色用户列表 -->
      <div class="kg-card">
        <div class="toolbar">
          <div class="toolbar-left">
            <div class="list-title-wrap">
              <span class="list-title">{{ selectedRoleName }}用户列表</span>
              <span class="list-count">共 {{ currentUsers.length }} 位</span>
            </div>
          </div>
          <div class="toolbar-right">
            <el-button :icon="Refresh" @click="loadAll">刷新</el-button>
          </div>
        </div>

        <div class="table-wrap">
          <el-table
            v-loading="loading"
            :data="currentUsers"
            style="width: 100%"
            :header-cell-style="{ background: 'transparent' }"
          >
            <el-table-column type="index" label="" width="56" align="center" />
            <el-table-column label="用户" min-width="220">
              <template #default="{ row }">
                <div class="cell-user">
                  <el-avatar :size="34" :src="row.userAvatar" class="user-avatar">
                    {{ (row.userName || row.userAccount || '?').charAt(0).toUpperCase() }}
                  </el-avatar>
                  <div class="user-info">
                    <span class="user-name">{{ row.userName || '未设置昵称' }}</span>
                    <span class="user-account">@{{ row.userAccount }}</span>
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="userProfile" label="简介" min-width="220" show-overflow-tooltip>
              <template #default="{ row }">
                <span class="profile-text">{{ row.userProfile || '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" align="center" fixed="right">
              <template #default="{ row }">
                <el-button size="small" @click="handleToggleRole(row)">
                  切换为{{ oppositeRoleName }}
                </el-button>
              </template>
            </el-table-column>

            <template #empty>
              <div class="empty-state">
                <el-icon :size="40" color="#c9cdd4"><UserFilled /></el-icon>
                <p class="empty-title">暂无{{ selectedRoleName }}用户</p>
                <p class="empty-desc">通过切换角色来调整用户归属</p>
              </div>
            </template>
          </el-table>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { Component } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UserFilled, User, Refresh, Switch, Lock } from '@element-plus/icons-vue'
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
.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 18px;
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

/* 角色概览卡片 */
.role-cards {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 18px;
  margin-bottom: 18px;
}

.role-card {
  background: var(--bg-card);
  border: 1px solid var(--border-2);
  border-radius: var(--r-lg);
  padding: 20px 22px;
  cursor: pointer;
  transition: all var(--t-base);
  position: relative;
  overflow: hidden;
}

.role-card::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, var(--brand-primary-soft) 0%, transparent 50%);
  opacity: 0;
  transition: opacity var(--t-base);
  pointer-events: none;
}

.role-card:hover {
  border-color: var(--border-1);
  box-shadow: var(--shadow-2);
  transform: translateY(-1px);
}

.role-card.active {
  border-color: var(--brand-primary);
  box-shadow: 0 4px 16px rgba(22, 93, 255, 0.12);
}

.role-card.active::before {
  opacity: 1;
}

.role-card-top {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 14px;
  position: relative;
}

.role-icon-wrap {
  width: 46px;
  height: 46px;
  border-radius: var(--r-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
}

.role-meta {
  flex: 1;
  min-width: 0;
}

.role-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-1);
  line-height: 1.3;
}

.role-code {
  font-size: 12px;
  color: var(--text-3);
  margin-top: 3px;
  font-family: 'SF Mono', Menlo, Consolas, monospace;
}

.role-count-badge {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  flex-shrink: 0;
}

.count-num {
  font-size: 24px;
  font-weight: 700;
  color: var(--brand-primary);
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.count-text {
  font-size: 11px;
  color: var(--text-3);
  margin-top: 2px;
}

.role-desc {
  font-size: 13px;
  color: var(--text-2);
  line-height: 1.6;
  margin: 0 0 14px;
  position: relative;
}

.role-perms {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  padding-top: 14px;
  border-top: 1px dashed var(--border-2);
  position: relative;
}

.perms-label {
  font-size: 12px;
  color: var(--text-3);
  margin-right: 2px;
}

.perm-chip {
  margin: 0;
}

/* 工具栏 */
.toolbar {
  padding: 16px 20px;
  margin: 0;
  border-bottom: 1px solid var(--border-2);
  background: #fbfcfd;
  border-radius: var(--r-lg) var(--r-lg) 0 0;
}

.toolbar-left {
  display: flex;
  gap: 10px;
  align-items: center;
}

.toolbar-right {
  display: flex;
  gap: 8px;
  align-items: center;
}

.list-title-wrap {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.list-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-1);
}

.list-count {
  font-size: 12px;
  color: var(--text-3);
}

.table-wrap {
  padding: 4px 12px 8px;
}

/* 用户单元格 */
.cell-user {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 2px 0;
}

.user-avatar {
  background: linear-gradient(135deg, #165dff 0%, #6366f1 100%);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  flex-shrink: 0;
}

.user-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.user-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-1);
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-account {
  font-size: 12px;
  color: var(--text-3);
}

.profile-text {
  font-size: 13px;
  color: var(--text-3);
}

/* 空态 */
.empty-state {
  padding: 64px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.empty-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-2);
  margin-top: 8px;
}

.empty-desc {
  font-size: 12px;
  color: var(--text-3);
}
</style>
