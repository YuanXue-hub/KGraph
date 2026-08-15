<template>
  <div class="ext-layout">
    <!-- 顶部页头：标题 + 副标题（标题复用全局 .page-title 渐变竖条） -->
    <div v-if="$slots['page-head']" class="ext-page-head">
      <slot name="page-head" />
    </div>

    <!-- 左右对称主体区：12:12 等宽 -->
    <el-row :gutter="20" class="ext-main">
      <el-col :span="12">
        <div class="ext-panel ext-panel--config">
          <div class="ext-panel-header">
            <span class="ext-panel-title">
              <span class="ext-bar" :style="{ background: `linear-gradient(180deg, ${themeColor}, var(--brand-accent))` }"></span>
              {{ configTitle }}
            </span>
            <div class="ext-panel-extra">
              <slot name="config-extra" />
            </div>
          </div>
          <div class="ext-panel-body">
            <slot name="config" />
          </div>
        </div>
      </el-col>
      <el-col :span="12">
        <div class="ext-panel ext-panel--result">
          <div class="ext-panel-header">
            <span class="ext-panel-title">
              <span class="ext-bar" :style="{ background: `linear-gradient(180deg, ${themeColor}, var(--brand-accent))` }"></span>
              {{ resultTitle }}
            </span>
            <div class="ext-panel-extra">
              <slot name="result-extra" />
            </div>
          </div>
          <div class="ext-panel-body">
            <slot name="result" />
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 底部历史记录区：全宽 -->
    <div class="ext-panel ext-panel--history" v-if="$slots.history">
      <div class="ext-panel-header">
        <span class="ext-panel-title">
          <span class="ext-bar" :style="{ background: `linear-gradient(180deg, ${themeColor}, var(--brand-accent))` }"></span>
          {{ historyTitle }}
        </span>
        <div class="ext-panel-extra">
          <slot name="history-extra" />
        </div>
      </div>
      <div class="ext-panel-body">
        <slot name="history" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  themeColor: string
  configTitle?: string
  resultTitle?: string
  historyTitle?: string
}>()
</script>

<style scoped>
.ext-layout {
  padding: 20px 24px 28px;
  max-width: 1600px;
  margin: 0 auto;
}

/* 顶部页头 */
.ext-page-head {
  margin-bottom: 18px;
}

.ext-page-head :deep(.page-title) {
  margin-bottom: 6px;
}

.ext-page-head :deep(.page-subtitle) {
  font-size: 13px;
  color: var(--text-3);
  font-weight: 400;
  letter-spacing: 0.2px;
  line-height: 1.6;
}

/* 主体对称区 */
.ext-main {
  margin-bottom: 18px;
  display: flex;
  align-items: stretch;
}

.ext-main > .el-col {
  display: flex;
}

/* 通用面板：kg-card 风格 */
.ext-panel {
  background: var(--bg-card);
  border-radius: var(--r-lg);
  border: 1px solid var(--border-2);
  box-shadow: var(--shadow-1);
  display: flex;
  flex-direction: column;
  width: 100%;
  overflow: hidden;
  transition: box-shadow var(--t-base);
}

.ext-panel:hover {
  box-shadow: var(--shadow-2);
}

.ext-panel--config,
.ext-panel--result {
  min-height: 520px;
}

.ext-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 20px;
  border-bottom: 1px solid var(--border-2);
  background: var(--bg-soft);
}

.ext-panel-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-1);
  display: flex;
  align-items: center;
  gap: 10px;
  letter-spacing: 0.2px;
}

/* 标题前渐变竖条 */
.ext-bar {
  width: 3px;
  height: 16px;
  border-radius: 2px;
  flex-shrink: 0;
}

.ext-panel-extra {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ext-panel-body {
  padding: 20px;
  flex: 1;
  overflow: auto;
}

.ext-panel--history {
  margin-bottom: 0;
}

.ext-panel--history .ext-panel-body {
  padding: 16px 20px;
}
</style>
