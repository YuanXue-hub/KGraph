<template>
  <el-container class="main-layout">
    <el-aside :width="isCollapse ? '64px' : '220px'" class="aside">
      <div class="logo">
        <KgLogo :size="isCollapse ? 28 : 24" />
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
            <span>图谱管理</span>
          </template>
          <el-menu-item index="/project">
            <el-icon><Files /></el-icon>
            <span>图谱项目管理</span>
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

        <el-menu-item index="/chat">
          <el-icon><ChatDotRound /></el-icon>
          <span>智能问答</span>
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
          <span class="header-greeting">{{ greeting }}</span>
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
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox, ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import KgLogo from '@/components/KgLogo.vue'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const isCollapse = ref(false)

const activeMenu = computed(() => route.path)

// 触发问候语定时刷新的响应式时间戳
const nowTick = ref(Date.now())
let greetingTimer: ReturnType<typeof setInterval> | null = null

const greeting = computed(() => {
  // 依赖 nowTick 以便定时刷新
  void nowTick.value
  const h = new Date().getHours()
  let period = '早上好'
  if (h >= 12 && h < 14) period = '中午好'
  else if (h >= 14 && h < 18) period = '下午好'
  else if (h >= 18 || h < 6) period = '晚上好'
  const name = userStore.userInfo?.userName || userStore.userInfo?.userAccount || ''
  return name ? `${period}，${name}` : period
})

onMounted(() => {
  // 每 30 秒刷新一次问候语，确保跨时段时实时变化
  greetingTimer = setInterval(() => {
    nowTick.value = Date.now()
  }, 30 * 1000)
})

onUnmounted(() => {
  if (greetingTimer) {
    clearInterval(greetingTimer)
    greetingTimer = null
  }
})

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
  transition: width 0.28s cubic-bezier(0.16, 1, 0.3, 1);
  overflow: hidden;
  position: relative;
}

/* 侧边栏右侧细分割线（更精致） */
.aside::after {
  content: '';
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 1px;
  background: linear-gradient(180deg, transparent 0%, #e5e6eb 20%, #e5e6eb 80%, transparent 100%);
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  border-bottom: 1px solid #f0f2f5;
  position: relative;
}

.logo::after {
  content: '';
  position: absolute;
  bottom: -1px;
  left: 16px;
  right: 16px;
  height: 1px;
  background: linear-gradient(90deg, transparent, #e5e6eb 30%, #e5e6eb 70%, transparent);
}

.logo-text {
  font-size: 19px;
  font-weight: 700;
  letter-spacing: 1.5px;
  background: linear-gradient(135deg, #1d2129 0%, #165dff 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}

.logo-icon {
  flex-shrink: 0;
}

.side-menu {
  border-right: none;
  background-color: transparent;
  padding: 8px 0;
}

.side-menu:not(.el-menu--collapse) {
  width: 220px;
}

/* 菜单项：浅色系，小图标 */
:deep(.el-menu-item) {
  color: #4e5969;
  height: 44px;
  line-height: 44px;
  margin: 2px 10px;
  border-radius: 10px;
  position: relative;
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

:deep(.el-menu-item .el-icon) {
  font-size: 15px;
  margin-right: 8px;
  color: #a9aeb8;
  transition: color 0.2s;
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
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(22, 93, 255, 0.1);
}

:deep(.el-menu-item.is-active .el-icon) {
  color: #165dff;
}

/* 激活态左侧指示条 */
:deep(.el-menu-item.is-active)::before {
  content: '';
  position: absolute;
  left: -10px;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 18px;
  border-radius: 0 2px 2px 0;
  background: linear-gradient(180deg, #165dff 0%, #6366f1 100%);
}

/* 子菜单标题 */
:deep(.el-sub-menu__title) {
  color: #4e5969;
  height: 44px;
  line-height: 44px;
  margin: 2px 10px;
  border-radius: 10px;
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

:deep(.el-sub-menu__title .el-icon) {
  font-size: 15px;
  margin-right: 8px;
  color: #a9aeb8;
  transition: color 0.2s;
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
  font-weight: 600;
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
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(0, 21, 41, 0.1);
  padding: 6px;
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
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.04);
  position: relative;
  z-index: 10;
}

.header::after {
  content: '';
  position: absolute;
  bottom: -1px;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, #e6e8eb 15%, #e6e8eb 85%, transparent);
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
  padding: 6px;
  border-radius: 8px;
  transition: all 0.2s;
}

.collapse-btn:hover {
  color: #165dff;
  background: #e8f3ff;
}

.header-greeting {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-2);
  letter-spacing: 0.3px;
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
  padding: 6px 12px;
  height: 44px;
  border-radius: 10px;
  transition: all 0.2s;
}

.user-info:hover {
  background: #f2f3f5;
}

.user-name {
  font-size: 14px;
  color: #303133;
  font-weight: 500;
}

.main {
  background-color: #f5f6f8;
  padding: 0;
  overflow: auto;
}
</style>
