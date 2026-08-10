<template>
  <div class="dl-page">
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
  padding: 20px;
}

.dl-tabs :deep(.el-tabs__header) {
  margin-bottom: 16px;
}

.dl-tabs :deep(.el-tabs__item) {
  font-weight: 500;
  font-size: 14px;
  height: 40px;
  line-height: 40px;
}
</style>
