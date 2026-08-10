<template>
  <div class="ext-layout">
    <!-- 左右对称主体区：12:12 等宽 -->
    <el-row :gutter="20" class="ext-main">
      <el-col :span="12">
        <div class="ext-panel ext-panel--config">
          <div class="ext-panel-header">
            <span class="ext-panel-title">
              <span class="ext-dot" :style="{ background: themeColor }"></span>
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
              <span class="ext-dot" :style="{ background: themeColor }"></span>
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
          <span class="ext-dot" :style="{ background: themeColor }"></span>
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
  padding: 20px 24px;
  max-width: 1600px;
  margin: 0 auto;
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

/* 通用面板 */
.ext-panel {
  background: #fff;
  border-radius: 12px;
  border: 1px solid #f0f2f5;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
  display: flex;
  flex-direction: column;
  width: 100%;
  overflow: hidden;
}

.ext-panel--config,
.ext-panel--result {
  min-height: 520px;
}

.ext-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #f0f2f5;
  background: #fafbfc;
}

.ext-panel-title {
  font-size: 15px;
  font-weight: 600;
  color: #1d2129;
  display: flex;
  align-items: center;
  gap: 8px;
}

.ext-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
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
