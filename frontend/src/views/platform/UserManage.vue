<template>
  <div class="page-container user-manage-page">
    <!-- 工具栏 -->
    <div v-if="!isAdmin" class="kg-card">
      <div class="empty-state">
        <el-icon :size="44" color="#c9cdd4"><Lock /></el-icon>
        <p class="empty-title">无权限访问</p>
        <p class="empty-desc">仅管理员可访问用户管理页面</p>
      </div>
    </div>

    <template v-else>
      <!-- 主体卡片 -->
      <div class="kg-card">
        <!-- 工具栏 -->
        <div class="toolbar">
          <div class="toolbar-left">
            <el-input
              v-model="searchForm.userName"
              placeholder="搜索用户名"
              class="search-input"
              clearable
              @keyup.enter="handleSearch"
              @clear="handleSearch"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
            <el-input
              v-model="searchForm.userAccount"
              placeholder="搜索账号"
              class="search-input"
              clearable
              @keyup.enter="handleSearch"
              @clear="handleSearch"
            >
              <template #prefix>
                <el-icon><User /></el-icon>
              </template>
            </el-input>
            <el-select
              v-model="searchForm.userRole"
              placeholder="角色"
              clearable
              class="role-select"
            >
              <el-option label="全部" value="" />
              <el-option label="管理员" value="admin" />
              <el-option label="普通用户" value="user" />
            </el-select>
            <el-button :icon="Search" @click="handleSearch">查询</el-button>
            <el-button :icon="Refresh" @click="handleReset">重置</el-button>
          </div>
          <div class="toolbar-right">
            <el-button type="primary" :icon="Plus" @click="openAdd">新增用户</el-button>
          </div>
        </div>

        <!-- 表格 -->
        <div class="table-wrap">
          <el-table
            v-loading="loading"
            :data="tableData"
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
            <el-table-column label="角色" width="120" align="center">
              <template #default="{ row }">
                <span class="status-dot" :class="row.userRole === 'admin' ? 'danger' : 'primary'"></span>
                <span class="status-text">{{ row.userRole === 'admin' ? '管理员' : '普通用户' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="userProfile" label="简介" min-width="200" show-overflow-tooltip>
              <template #default="{ row }">
                <span class="profile-text">{{ row.userProfile || '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="创建时间" width="180" align="center">
              <template #default="{ row }">
                <span class="time-cell">{{ formatTime(row.createTime) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="130" align="center" fixed="right">
              <template #default="{ row }">
                <el-button size="small" @click="openEdit(row)">编辑</el-button>
                <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
              </template>
            </el-table-column>

            <template #empty>
              <div class="empty-state">
                <el-icon :size="40" color="#c9cdd4"><UserFilled /></el-icon>
                <p class="empty-title">暂无用户数据</p>
                <p class="empty-desc">点击右上角「新增用户」开始添加</p>
              </div>
            </template>
          </el-table>
        </div>

        <div class="pagination-wrapper">
          <el-pagination
            v-model:current-page="pageNum"
            v-model:page-size="pageSize"
            :page-sizes="[10, 20, 50]"
            :total="total"
            layout="total, sizes, prev, pager, next, jumper"
            @size-change="handleSizeChange"
            @current-change="loadList"
          />
        </div>
      </div>

      <!-- 新增/编辑对话框 -->
      <el-dialog
        v-model="dialogVisible"
        :title="isEdit ? '编辑用户' : '新增用户'"
        width="560px"
        @closed="resetForm"
      >
        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-width="90px"
        >
          <el-form-item label="昵称" prop="userName">
            <el-input v-model="form.userName" placeholder="请输入昵称" />
          </el-form-item>
          <el-form-item label="账号" prop="userAccount">
            <el-input
              v-model="form.userAccount"
              placeholder="请输入账号"
              :disabled="isEdit"
            />
          </el-form-item>
          <el-form-item label="头像URL">
            <el-input v-model="form.userAvatar" placeholder="请输入头像地址" />
          </el-form-item>
          <el-form-item label="简介">
            <el-input
              v-model="form.userProfile"
              type="textarea"
              :rows="3"
              placeholder="请输入简介"
            />
          </el-form-item>
          <el-form-item label="角色" prop="userRole">
            <el-select v-model="form.userRole" placeholder="请选择角色" style="width: 100%">
              <el-option label="管理员" value="admin" />
              <el-option label="普通用户" value="user" />
            </el-select>
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
        </template>
      </el-dialog>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Search, Refresh, Edit, Delete, User, UserFilled, Lock } from '@element-plus/icons-vue'
import { userApi } from '@/api'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const isAdmin = userStore.isAdmin

interface UserRow {
  id: string
  userAccount: string
  userName?: string
  userAvatar?: string
  userProfile?: string
  userRole?: string
  createTime?: string
}

const loading = ref(false)
const tableData = ref<UserRow[]>([])
const total = ref(0)
const pageNum = ref(1)
const pageSize = ref(10)

const searchForm = reactive({
  userName: '',
  userAccount: '',
  userRole: ''
})

const dialogVisible = ref(false)
const isEdit = ref(false)
const submitting = ref(false)
const formRef = ref<FormInstance>()

const form = reactive({
  id: '' as string,
  userName: '',
  userAccount: '',
  userAvatar: '',
  userProfile: '',
  userRole: 'user'
})

const rules: FormRules = {
  userName: [{ required: true, message: '请输入昵称', trigger: 'blur' }],
  userAccount: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  userRole: [{ required: true, message: '请选择角色', trigger: 'change' }]
}

async function loadList() {
  loading.value = true
  try {
    const res = await userApi.listPage({
      pageNum: pageNum.value,
      pageSize: pageSize.value,
      userName: searchForm.userName || undefined,
      userAccount: searchForm.userAccount || undefined,
      userRole: searchForm.userRole || undefined
    })
    const data = res.data || ({} as any)
    tableData.value = data.records || []
    // total 可能是字符串（后端 Long 序列化为 String）
    total.value = Number(data.total) || 0
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  pageNum.value = 1
  loadList()
}

function handleReset() {
  searchForm.userName = ''
  searchForm.userAccount = ''
  searchForm.userRole = ''
  pageNum.value = 1
  loadList()
}

function handleSizeChange(size: number) {
  pageSize.value = size
  pageNum.value = 1
  loadList()
}

function openAdd() {
  isEdit.value = false
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: UserRow) {
  isEdit.value = true
  resetForm()
  form.id = row.id
  form.userName = row.userName || ''
  form.userAccount = row.userAccount || ''
  form.userAvatar = row.userAvatar || ''
  form.userProfile = row.userProfile || ''
  form.userRole = row.userRole || 'user'
  dialogVisible.value = true
}

function resetForm() {
  form.id = ''
  form.userName = ''
  form.userAccount = ''
  form.userAvatar = ''
  form.userProfile = ''
  form.userRole = 'user'
  formRef.value?.clearValidate()
}

async function handleSubmit() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  submitting.value = true
  try {
    if (isEdit.value) {
      await userApi.update({
        id: form.id,
        userName: form.userName,
        userAvatar: form.userAvatar,
        userProfile: form.userProfile,
        userRole: form.userRole
      })
      ElMessage.success('编辑成功')
    } else {
      await userApi.add({
        userName: form.userName,
        userAccount: form.userAccount,
        userAvatar: form.userAvatar,
        userProfile: form.userProfile,
        userRole: form.userRole
      })
      ElMessage.success('新增成功')
    }
    dialogVisible.value = false
    loadList()
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row: UserRow) {
  try {
    await ElMessageBox.confirm(
      `确定删除用户「${row.userName || row.userAccount}」？`,
      '提示',
      { type: 'warning' }
    )
    await userApi.delete(row.id)
    ElMessage.success('删除成功')
    // 删除后若当前页无数据，回到上一页
    if (tableData.value.length === 1 && pageNum.value > 1) {
      pageNum.value -= 1
    }
    loadList()
  } catch {
    // 用户取消，不做处理
  }
}

function formatTime(t?: string) {
  if (!t) return '-'
  return t.replace('T', ' ').substring(0, 19)
}

onMounted(() => {
  if (isAdmin) {
    loadList()
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
  flex-wrap: wrap;
}

.toolbar-right {
  display: flex;
  gap: 8px;
  align-items: center;
}

.search-input {
  width: 200px;
}

.role-select {
  width: 130px;
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

/* 状态点 */
.status-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: middle;
}

.status-dot.primary {
  background: #165dff;
  box-shadow: 0 0 0 3px rgba(22, 93, 255, 0.12);
}

.status-dot.danger {
  background: #f53f3f;
  box-shadow: 0 0 0 3px rgba(245, 63, 63, 0.12);
}

.status-text {
  font-size: 12px;
  color: var(--text-2);
  vertical-align: middle;
}

.profile-text {
  font-size: 13px;
  color: var(--text-3);
}

.time-cell {
  font-size: 12px;
  color: var(--text-3);
  font-variant-numeric: tabular-nums;
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

.pagination-wrapper {
  padding: 12px 20px 16px;
  margin: 0;
  border-top: 1px solid var(--border-2);
  display: flex;
  justify-content: flex-end;
}
</style>
