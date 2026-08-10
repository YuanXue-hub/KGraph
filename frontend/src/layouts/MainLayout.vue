<template>
  <el-container class="main-layout">
    <el-aside :width="isCollapse ? '64px' : '220px'" class="aside">
      <div class="logo">
        <svg class="logo-icon" viewBox="0 0 32 32" :width="isCollapse ? 28 : 24" :height="isCollapse ? 28 : 24">
          <defs>
            <radialGradient id="kgNodeGrad" cx="35%" cy="35%">
              <stop offset="0%" stop-color="#4e5969" />
              <stop offset="100%" stop-color="#1d2129" />
            </radialGradient>
            <radialGradient id="kgCenterGrad" cx="35%" cy="35%">
              <stop offset="0%" stop-color="#4080ff" />
              <stop offset="100%" stop-color="#165dff" />
            </radialGradient>
          </defs>
          <!-- 连线：六边形网络 -->
          <g stroke="#a9aeb8" stroke-width="0.5" opacity="0.6" fill="none">
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
          <!-- 外围节点：立体渐变球 -->
          <g fill="url(#kgNodeGrad)">
            <circle cx="25" cy="16" r="1.8" />
            <circle cx="20.5" cy="8.2" r="1.8" />
            <circle cx="11.5" cy="8.2" r="1.8" />
            <circle cx="7" cy="16" r="1.8" />
            <circle cx="11.5" cy="23.8" r="1.8" />
            <circle cx="20.5" cy="23.8" r="1.8" />
          </g>
          <!-- 中心节点：蓝色立体球 -->
          <circle cx="16" cy="16" r="2.5" fill="url(#kgCenterGrad)" />
        </svg>
        <span v-show="!isCollapse" class="logo-text">KGraph</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapse"
        router
        class="side-menu"
      >
        <el-menu-item index="/home">
          <el-icon><HomeFilled /></el-icon>
          <span>首页</span>
        </el-menu-item>

        <el-sub-menu index="platform">
          <template #title>
            <el-icon><Setting /></el-icon>
            <span>平台管理</span>
          </template>
          <el-menu-item index="/platform/user">
            <el-icon><User /></el-icon>
            <span>用户管理</span>
          </el-menu-item>
          <el-menu-item index="/platform/role">
            <el-icon><UserFilled /></el-icon>
            <span>角色管理</span>
          </el-menu-item>
          <el-menu-item index="/platform/profile">
            <el-icon><Avatar /></el-icon>
            <span>个人信息</span>
          </el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="graph-manage">
          <template #title>
            <el-icon><Folder /></el-icon>
            <span>图谱项目管理</span>
          </template>
          <el-menu-item index="/project">
            <el-icon><Files /></el-icon>
            <span>知识图谱管理</span>
          </el-menu-item>
          <el-menu-item index="/model">
            <el-icon><Share /></el-icon>
            <span>图谱模型管理</span>
          </el-menu-item>
        </el-sub-menu>

        <el-menu-item index="/corpus">
          <el-icon><Document /></el-icon>
          <span>语料管理</span>
        </el-menu-item>

        <el-sub-menu index="extraction">
          <template #title>
            <el-icon><MagicStick /></el-icon>
            <span>知识抽取</span>
          </template>
          <el-menu-item index="/extraction/structure">
            <el-icon><Grid /></el-icon>
            <span>结构化抽取</span>
          </el-menu-item>
          <el-menu-item index="/extraction/kos">
            <el-icon><Collection /></el-icon>
            <span>KOS 抽取</span>
          </el-menu-item>
          <el-menu-item index="/extraction/dl">
            <el-icon><Cpu /></el-icon>
            <span>深度学习抽取</span>
          </el-menu-item>
          <el-menu-item index="/extraction">
            <el-icon class="robot-icon"><svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor"><path d="M12 2a2 2 0 0 1 2 2v1h1a3 3 0 0 1 3 3v1h1a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1h-1v1a3 3 0 0 1-3 3H8a3 3 0 0 1-3-3v-1H4a1 1 0 0 1-1-1V10a1 1 0 0 1 1-1h1V8a3 3 0 0 1 3-3h1V4a2 2 0 0 1 2-2zM9 9a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3zm6 0a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3zm-3 4a2 2 0 0 0-2 2v1h4v-1a2 2 0 0 0-2-2z"/></svg></el-icon>
            <span>LLM 抽取</span>
          </el-menu-item>
        </el-sub-menu>

        <el-menu-item index="/explore">
          <el-icon><DataAnalysis /></el-icon>
          <span>图谱探索</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="header-left">
          <el-icon class="collapse-btn" @click="isCollapse = !isCollapse">
            <Fold v-if="!isCollapse" />
            <Expand v-else />
          </el-icon>
          <span class="system-name">知识图谱管理系统</span>
        </div>
        <div class="header-right">
          <el-dropdown @command="handleCommand">
            <span class="user-info">
              <el-avatar :size="32" :src="userStore.userInfo?.userAvatar">
                {{ avatarText }}
              </el-avatar>
              <span class="user-name">{{ userStore.userInfo?.userName || userStore.userInfo?.userAccount || '用户' }}</span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">
                  <el-icon><Avatar /></el-icon> 个人信息
                </el-dropdown-item>
                <el-dropdown-item command="logout" divided>
                  <el-icon><SwitchButton /></el-icon> 退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox, ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const isCollapse = ref(false)

const activeMenu = computed(() => route.path)

const avatarText = computed(() => {
  const name = userStore.userInfo?.userName || userStore.userInfo?.userAccount || 'U'
  return name.charAt(0).toUpperCase()
})

async function handleCommand(command: string) {
  if (command === 'logout') {
    try {
      await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
        type: 'warning'
      })
      await userStore.logout()
      ElMessage.success('已退出登录')
      router.push('/login')
    } catch {
      // 取消
    }
  } else if (command === 'profile') {
    router.push('/platform/profile')
  }
}
</script>

<style scoped>
.main-layout {
  height: 100vh;
}

/* 侧边栏：浅色系，浅灰白底 */
.aside {
  background-color: #fafbfc;
  border-right: 1px solid #f0f2f5;
  transition: width 0.28s;
  overflow: hidden;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border-bottom: 1px solid #f0f2f5;
}

.logo-text {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: 2px;
  color: #1d2129;
}

.logo-icon {
  flex-shrink: 0;
}

.side-menu {
  border-right: none;
  background-color: transparent;
}

.side-menu:not(.el-menu--collapse) {
  width: 220px;
}

/* 菜单项：浅色系，小图标 */
:deep(.el-menu-item) {
  color: #4e5969;
  height: 44px;
  line-height: 44px;
  margin: 2px 8px;
  border-radius: 8px;
}

:deep(.el-menu-item .el-icon) {
  font-size: 15px;
  margin-right: 8px;
  color: #a9aeb8;
}

:deep(.el-menu-item:hover) {
  background-color: #f2f3f5 !important;
  color: #1d2129;
}

:deep(.el-menu-item:hover .el-icon) {
  color: #4e5969;
}

:deep(.el-menu-item.is-active) {
  background-color: #e8f3ff !important;
  color: #165dff !important;
  font-weight: 500;
}

:deep(.el-menu-item.is-active .el-icon) {
  color: #165dff;
}

/* 子菜单标题 */
:deep(.el-sub-menu__title) {
  color: #4e5969;
  height: 44px;
  line-height: 44px;
  margin: 2px 8px;
  border-radius: 8px;
}

:deep(.el-sub-menu__title .el-icon) {
  font-size: 15px;
  margin-right: 8px;
  color: #a9aeb8;
}

:deep(.el-sub-menu__title:hover) {
  background-color: #f2f3f5 !important;
  color: #1d2129;
}

:deep(.el-sub-menu__title:hover .el-icon) {
  color: #4e5969;
}

:deep(.el-sub-menu.is-active > .el-sub-menu__title) {
  color: #165dff;
  font-weight: 500;
}

:deep(.el-sub-menu.is-active > .el-sub-menu__title .el-icon) {
  color: #165dff;
}

/* 子菜单展开区背景 */
:deep(.el-menu--inline) {
  background-color: transparent !important;
}

/* 折叠态弹出菜单 */
:deep(.el-menu--popup) {
  background-color: #fafbfc;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

/* 折叠状态下图标居中 */
:deep(.el-menu--collapse .el-menu-item .el-icon),
:deep(.el-menu--collapse .el-sub-menu__title .el-icon) {
  margin-right: 0;
}

.header {
  background-color: #fff;
  border-bottom: 1px solid #e6e8eb;
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.06);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.collapse-btn {
  font-size: 20px;
  cursor: pointer;
  color: #5a5e66;
}

.collapse-btn:hover {
  color: #165dff;
}

.system-name {
  font-size: 18px;
  font-weight: 600;
  color: #1d2129;
}

.header-right {
  display: flex;
  align-items: center;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 0 8px;
  height: 60px;
}

.user-name {
  font-size: 14px;
  color: #303133;
}

.main {
  background-color: #f5f6f8;
  padding: 0;
  overflow: auto;
}
</style>
