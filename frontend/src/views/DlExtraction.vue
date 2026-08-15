<template>
  <div class="dl-page">
    <!-- 顶部页头 -->
    <div class="page-head">
      <h2 class="page-title">深度学习抽取</h2>
      <p class="page-subtitle">数据标注 → 模型训练 → 抽取应用 → 模型效果，全流程深度学习知识抽取</p>
    </div>

    <!-- 顶部 4 个 Tab 页签 -->
    <el-tabs v-model="activeTab" class="dl-tabs" type="card" @tab-change="onTabChange">
      <el-tab-pane label="数据标注" name="annotation">
        <DataAnnotation />
      </el-tab-pane>
      <el-tab-pane label="模型训练" name="train">
        <ModelTrain />
      </el-tab-pane>
      <el-tab-pane label="抽取应用" name="extract">
        <DlExtractApp />
      </el-tab-pane>
      <el-tab-pane label="模型效果" name="effect">
        <ModelEffect />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref } from 'vue'
import DataAnnotation from '@/components/dl/DataAnnotation.vue'
import ModelTrain from '@/components/dl/ModelTrain.vue'
import DlExtractApp from '@/components/dl/DlExtractApp.vue'
import ModelEffect from '@/components/dl/ModelEffect.vue'

// 当前激活的 tab，默认进入「抽取应用」
const activeTab = ref('extract')

// tab 切换后触发 resize，让 ModelTrain/ModelEffect 的 ECharts 重新计算尺寸
function onTabChange(name: string | number) {
  if (name === 'train' || name === 'effect') {
    nextTick(() => {
      window.dispatchEvent(new Event('resize'))
    })
  }
}
</script>

<style scoped>
.dl-page {
  padding: 20px 24px 28px;
  max-width: 1600px;
  margin: 0 auto;
}

.page-head {
  margin-bottom: 18px;
}

.page-subtitle {
  font-size: 13px;
  color: var(--text-3);
  font-weight: 400;
  letter-spacing: 0.2px;
  line-height: 1.6;
}

.dl-tabs :deep(.el-tabs__header) {
  margin-bottom: 18px;
  border-bottom: 1px solid var(--border-2);
}

.dl-tabs :deep(.el-tabs__nav) {
  border: none;
  gap: 8px;
}

.dl-tabs :deep(.el-tabs__item) {
  font-weight: 500;
  font-size: 14px;
  height: 40px;
  line-height: 40px;
  color: var(--text-2);
  background: var(--bg-soft);
  border: 1px solid var(--border-2) !important;
  border-radius: var(--r-md) var(--r-md) 0 0;
  border-bottom: none !important;
  transition: all var(--t-fast);
  padding: 0 22px;
}

.dl-tabs :deep(.el-tabs__item:hover) {
  color: var(--brand-primary);
  border-color: var(--border-1) !important;
}

.dl-tabs :deep(.el-tabs__item.is-active) {
  color: var(--brand-primary);
  background: var(--bg-card);
  border-color: var(--border-2) !important;
  border-bottom: 1px solid var(--bg-card) !important;
  font-weight: 600;
  position: relative;
  top: 1px;
}

.dl-tabs :deep(.el-tabs__item.is-active::before) {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, var(--brand-primary), var(--brand-accent));
  border-radius: var(--r-md) var(--r-md) 0 0;
}
</style>
