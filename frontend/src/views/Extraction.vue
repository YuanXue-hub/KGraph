<template>
  <div class="llm-ext-page">
    <el-tabs v-model="pageTab" class="llm-ext-page-tabs" type="card">
      <el-tab-pane label="知识抽取" name="extract">
        <ExtractionLayout
            theme-color="#409eff"
            config-title="抽取配置"
            result-title="抽取结果"
            history-title="抽取历史记录"
          >
            <template #config>
              <el-tabs v-model="activeConfigTab" class="config-tabs">
                <el-tab-pane label="抽取配置" name="extract">
                  <el-form label-width="100px" class="ext-form">
                    <el-form-item label="所属项目">
                      <el-select v-model="projectId" placeholder="选择项目" filterable style="width: 100%" @change="onProjectChange">
                        <el-option v-for="p in projects" :key="p.id" :label="p.projectName" :value="p.id" />
                      </el-select>
                    </el-form-item>

                    <el-form-item label="图谱模型">
                      <el-select v-model="modelId" placeholder="请先选择项目" filterable style="width: 100%" @change="onModelChange">
                        <el-option v-for="m in models" :key="m.id" :label="m.modelName" :value="m.id" />
                      </el-select>
                    </el-form-item>

                    <el-form-item label="抽取模型">
                      <el-select v-model="extractLlmModelId" placeholder="选择 LLM 模型" filterable :loading="extractLlmLoading" style="width: 100%">
                        <el-option v-for="m in extractLlmModels" :key="m.id" :label="m.displayName || m.modelName" :value="m.id" />
                      </el-select>
                    </el-form-item>

                    <el-form-item label="语料来源">
                      <div class="corpus-source">
                        <div class="corpus-tabs">
                          <div class="corpus-tab" :class="{ active: corpusMode === 'corpus' }" @click="onCorpusModeChange('corpus')">
                            选择语料
                          </div>
                          <div class="corpus-tab" :class="{ active: corpusMode === 'manual' }" @click="onCorpusModeChange('manual')">
                            手动输入
                          </div>
                        </div>
                        <div class="corpus-content">
                          <el-select v-if="corpusMode === 'corpus'" v-model="corpusId" placeholder="选择语料" filterable style="width: 100%" @change="loadCorpusContent">
                            <el-option v-for="c in corpusList" :key="c.id" :label="c.title" :value="c.id">
                              <span style="display: inline-flex; justify-content: space-between; width: 100%; gap: 12px; align-items: center;">
                                <span style="font-weight: 500; color: #1f2329;">{{ c.title }}</span>
                                <span v-if="projectNameById(c.projectId)" style="color: #86909c; font-size: 12px; flex-shrink: 0;">
                                  {{ projectNameById(c.projectId) }}
                                </span>
                              </span>
                            </el-option>
                          </el-select>
                          <el-input
                            v-model="inputText"
                            type="textarea"
                            :rows="8"
                            :placeholder="corpusMode === 'corpus' ? '选择语料后，文本内容将展示在此' : '请输入需要抽取的文本内容'"
                            :disabled="corpusMode === 'corpus'"
                          />
                        </div>
                      </div>
                    </el-form-item>

                    <el-form-item>
                      <el-button type="primary" :loading="extracting" :disabled="!canExtract" @click="handleExtract" class="ext-btn-action">
                        开始抽取
                      </el-button>
                    </el-form-item>
                  </el-form>
                </el-tab-pane>

                <el-tab-pane label="实体关系配置" name="ontology">
                  <div class="ontology-config">
                    <div class="ontology-section">
                      <h4 class="ontology-title">实体类型</h4>
                      <p class="ontology-sub">从模型加载: {{ modelEntityTypes.length }} 个 | 自定义: {{ customEntityTypes.length }} 个</p>
                      <div class="tag-list">
                        <el-tag
                          v-for="t in modelEntityTypes"
                          :key="'m-' + t"
                          closable
                          type="info"
                          size="large"
                          @close="removeModelEntity(t)"
                          class="ontology-tag"
                        >{{ t }}</el-tag>
                        <el-tag
                          v-for="(t, i) in customEntityTypes"
                          :key="'c-' + i"
                          closable
                          type="primary"
                          size="large"
                          @close="customEntityTypes.splice(i, 1)"
                          class="ontology-tag"
                        >{{ t }}</el-tag>
                      </div>
                      <div class="tag-input-row">
                        <el-input v-model="newEntityType" placeholder="输入实体类型名称" @keyup.enter="addEntityType" />
                        <el-button type="primary" @click="addEntityType">添加</el-button>
                      </div>
                    </div>

                    <el-divider />

                    <div class="ontology-section">
                      <h4 class="ontology-title">关系类型</h4>
                      <p class="ontology-sub">从模型加载: {{ modelRelationTypes.length }} 个 | 自定义: {{ customRelationTypes.length }} 个</p>
                      <div class="tag-list">
                        <el-tag
                          v-for="t in modelRelationTypes"
                          :key="'m-' + t"
                          closable
                          type="info"
                          size="large"
                          @close="removeModelRelation(t)"
                          class="ontology-tag"
                        >{{ t }}</el-tag>
                        <el-tag
                          v-for="(t, i) in customRelationTypes"
                          :key="'c-' + i"
                          closable
                          type="success"
                          size="large"
                          @close="customRelationTypes.splice(i, 1)"
                          class="ontology-tag"
                        >{{ t }}</el-tag>
                      </div>
                      <div class="tag-input-row">
                        <el-input v-model="newRelationType" placeholder="输入关系类型名称" @keyup.enter="addRelationType" />
                        <el-button type="success" @click="addRelationType">添加</el-button>
                      </div>
                    </div>

                    <el-divider />

                    <div class="ontology-actions">
                      <el-button @click="clearOntologyConfig">清空配置</el-button>
                      <el-button type="primary" @click="activeConfigTab = 'extract'">返回抽取</el-button>
                    </div>
                  </div>
                </el-tab-pane>
              </el-tabs>
            </template>

            <template #result-extra>
              <div v-if="result" class="ext-stat-tags">
                <el-tag type="primary" effect="plain">实体 {{ result.entities?.length || 0 }}</el-tag>
                <el-tag type="success" effect="plain">关系 {{ result.relations?.length || 0 }}</el-tag>
                <el-tag type="warning" effect="plain" v-if="result.costTime">耗时 {{ result.costTime }}ms</el-tag>
              </div>
            </template>

            <template #result>
              <el-empty v-if="!result" description="点击「开始抽取」查看结果" />

              <div v-else class="ext-result">
                <div v-if="highlightedText" class="ext-highlight-box">
                  <h4 class="ext-section-title">原文标注</h4>
                  <div class="ext-highlight-text" v-html="highlightedText"></div>
                </div>

                <el-tabs class="mt-12">
                  <el-tab-pane :label="`实体列表 (${entities.length})`">
                    <el-table :data="pagedEntities" border>
                      <el-table-column type="index" width="60" align="center" :index="(i: number) => (entityPage - 1) * ENTITY_PAGE_SIZE + i + 1" />
                      <el-table-column prop="name" label="实体名称" min-width="180" />
                      <el-table-column prop="type" label="类型" width="140">
                        <template #default="{ row }">
                          <el-tag :color="typeColorMap[row.type]" effect="dark">{{ row.type }}</el-tag>
                        </template>
                      </el-table-column>
                      <el-table-column label="属性" min-width="300">
                        <template #default="{ row }">
                          <span v-if="!row.properties || !Object.keys(row.properties).length">-</span>
                          <el-tag v-for="(v, k) in row.properties" :key="k" class="entity-tag" style="margin: 2px 4px 2px 0;">{{ k }}: {{ v }}</el-tag>
                        </template>
                      </el-table-column>
                    </el-table>
                    <div class="ext-pagination" v-if="entities.length > ENTITY_PAGE_SIZE">
                      <el-pagination v-model:current-page="entityPage" :page-size="ENTITY_PAGE_SIZE" :total="entities.length" layout="total, prev, pager, next" />
                    </div>
                  </el-tab-pane>

                  <el-tab-pane :label="`关系列表 (${relations.length})`">
                    <el-table :data="pagedRelations" border>
                      <el-table-column type="index" width="60" align="center" :index="(i: number) => (relPage - 1) * REL_PAGE_SIZE + i + 1" />
                      <el-table-column prop="head" label="头实体" min-width="180" />
                      <el-table-column prop="relation" label="关系" width="140">
                        <template #default="{ row }">
                          <el-tag type="success">{{ row.relation }}</el-tag>
                        </template>
                      </el-table-column>
                      <el-table-column prop="tail" label="尾实体" min-width="180" />
                      <el-table-column label="属性" min-width="280">
                        <template #default="{ row }">
                          <span v-if="!row.properties || !Object.keys(row.properties).length">-</span>
                          <el-tag v-for="(v, k) in row.properties" :key="k" class="entity-tag" style="margin: 2px 4px 2px 0;">{{ k }}: {{ v }}</el-tag>
                        </template>
                      </el-table-column>
                    </el-table>
                    <div class="ext-pagination" v-if="relations.length > REL_PAGE_SIZE">
                      <el-pagination v-model:current-page="relPage" :page-size="REL_PAGE_SIZE" :total="relations.length" layout="total, prev, pager, next" />
                    </div>
                  </el-tab-pane>
                </el-tabs>
              </div>
            </template>

            <template #history-extra>
              <el-button size="small" :icon="Refresh" @click="loadHistory">刷新</el-button>
            </template>

            <template #history>
              <el-table :data="history" border v-loading="historyLoading" size="small">
                <el-table-column type="index" min-width="50" align="center" />
                <el-table-column prop="extractionType" label="类型" min-width="70" align="center">
                  <template #default="{ row }">
                    <el-tag :type="extractionTypeColor(row.extractionType)" size="small">{{ row.extractionType || 'LLM' }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="modelId" label="模型ID" min-width="110" align="center" />
                <el-table-column prop="duration" label="耗时(ms)" min-width="90" align="center" />
                <el-table-column prop="status" label="状态" min-width="70" align="center">
                  <template #default="{ row }">
                    <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="createTime" label="抽取时间" min-width="150">
                  <template #default="{ row }">{{ formatTime(row.createTime) }}</template>
                </el-table-column>
                <el-table-column label="操作" min-width="180" align="center">
                  <template #default="{ row }">
                    <el-button size="small" @click="viewHistory(row)">查看</el-button>
                    <el-button size="small" @click="exportExtractionTask(row)">导出</el-button>
                    <el-button size="small" type="danger" @click="deleteHistory(row)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
              <div class="ext-pagination">
                <el-pagination v-model:current-page="histPage" v-model:page-size="histSize" :total="histTotal" layout="total, prev, pager, next" @current-change="loadHistory" />
              </div>
            </template>
        </ExtractionLayout>
      </el-tab-pane>

      <el-tab-pane label="质量评估" name="evaluate">
        <div class="eval-layout">
          <!-- 评估配置 -->
          <div class="eval-panel">
            <div class="eval-panel-header">
              <span class="eval-panel-title"><span class="eval-bar"></span>评估配置</span>
            </div>
            <div class="eval-panel-body">
              <div class="eval-config">
                <div class="eval-task-row">
                  <span class="eval-label">抽取结果</span>
                  <el-select
                    v-model="evalTaskId"
                    filterable
                    placeholder="选择抽取任务"
                    style="flex: 1"
                    :loading="evalHistLoading"
                    @change="onEvalTaskChange"
                  >
                    <el-option
                      v-for="t in evalHistory"
                      :key="t.id"
                      :value="t.id"
                      :label="`#${t.id} · ${t.extractionType || 'LLM'} · ${formatTime(t.createTime)} · ${statusText(t.status)}`"
                    />
                  </el-select>
                  <el-button :icon="Refresh" @click="loadEvalHistory">刷新</el-button>
                </div>

                <div v-if="evalTarget" class="eval-meta">
                  <el-tag type="primary" effect="plain">实体 {{ evalTarget.entities?.length || 0 }}</el-tag>
                  <el-tag type="success" effect="plain">关系 {{ evalTarget.relations?.length || 0 }}</el-tag>
                  <span class="eval-meta-text">评估对象：抽取任务 #{{ evalTaskId }}；内在指标全量计算，LLM 裁判{{ evalSampleSize === 0 ? '全量判定' : '按抽样判定' }}；已选指标 {{ selectedMetricKeys.length }}/{{ EVAL_METRICS.length }}</span>
                </div>

                <div v-if="evalTarget" class="eval-text-row">
                  <span class="eval-label">评估语料</span>
                  <template v-if="evalTextUsed">
                    <el-tag :type="evalTextOverride ? 'warning' : 'info'" effect="plain" size="small">
                      {{ evalTextOverride ? (evalTextOverrideFrom === 'corpus' ? '已选语料' : '手动指定') : '自动带入' }}
                    </el-tag>
                    <span class="eval-meta-text">{{ evalTextUsed.length }} 字</span>
                  </template>
                  <el-tag v-else type="danger" effect="plain" size="small">缺少原文</el-tag>
                  <el-button size="small" @click="openCorpusPick">选择语料</el-button>
                  <el-button size="small" @click="evalManualVisible = true">手动输入</el-button>
                  <el-button v-if="evalTextOverride" size="small" text type="danger" @click="clearEvalTextOverride">恢复自动</el-button>
                </div>

                <div class="eval-metrics-row">
                  <span class="eval-label">评估指标</span>
                  <div class="eval-metrics-group">
                    <el-checkbox
                      v-for="m in EVAL_METRICS"
                      :key="m.key"
                      v-model="evalMetrics[m.key]"
                    >{{ m.name }}</el-checkbox>
                  </div>
                  <el-button size="small" text type="primary" @click="toggleAllMetrics">
                    {{ isAllMetricsSelected ? '全不选' : '全选' }}
                  </el-button>
                </div>

                <div class="eval-actions">
                  <span class="eval-label">裁判模型</span>
                  <el-select v-model="evalLlmModelId" :loading="evalLlmLoading" placeholder="默认模型" clearable style="width: 170px">
                    <el-option v-for="m in evalLlmModels" :key="m.id" :value="m.id" :label="m.displayName" />
                  </el-select>
                  <span class="eval-label">LLM 裁判抽样数量</span>
                  <el-select v-model="evalSampleSize" style="width: 110px">
                    <el-option v-for="n in [10, 20, 30, 50]" :key="n" :value="n" :label="`${n} 条`" />
                    <el-option :value="0" label="全部" />
                  </el-select>
                  <el-button type="primary" :loading="evaluating" :disabled="!evalTarget" @click="handleEvaluate">开始评估</el-button>
                </div>
              </div>
            </div>
          </div>

          <!-- 评估原文：选择语料对话框 -->
          <el-dialog v-model="evalCorpusVisible" title="选择评估原文语料" width="520px" append-to-body>
            <el-select
              v-model="evalCorpusPickId"
              filterable
              placeholder="搜索并选择语料"
              style="width: 100%"
            >
              <el-option v-for="c in corpusList" :key="c.id" :label="c.title" :value="c.id" />
            </el-select>
            <div v-if="evalCorpusPickPreview" class="eval-corpus-preview">{{ evalCorpusPickPreview }}</div>
            <template #footer>
              <el-button @click="evalCorpusVisible = false">取消</el-button>
              <el-button type="primary" :disabled="!evalCorpusPickId" @click="confirmCorpusPick">使用该语料原文</el-button>
            </template>
          </el-dialog>

          <!-- 评估原文：手动输入对话框 -->
          <el-dialog v-model="evalManualVisible" title="手动输入评估原文" width="640px" append-to-body>
            <el-input
              v-model="evalManualText"
              type="textarea"
              :rows="10"
              placeholder="粘贴待评估的原文文本（需与抽取结果对应）"
            />
            <template #footer>
              <el-button @click="evalManualVisible = false">取消</el-button>
              <el-button type="primary" :disabled="!evalManualText.trim()" @click="confirmManualText">确定</el-button>
            </template>
          </el-dialog>

          <!-- 评估报告（内在指标 + LLM 裁判） -->
          <div v-if="evalResult" class="eval-panel">
            <div class="eval-panel-header">
              <span class="eval-panel-title"><span class="eval-bar"></span>评估报告</span>
              <div class="eval-header-extra">
                <el-tag v-if="evalResult?.evaluationId" type="warning" effect="plain">历史 #{{ evalResult?.evaluationId }}</el-tag>
                <el-tag v-if="evalResult?.judgeModel" type="primary" effect="plain">裁判模型 {{ evalResult?.judgeModel }}</el-tag>
                <el-tag v-if="evalResult?.duration" type="info" effect="plain">耗时 {{ evalResult?.duration }}ms</el-tag>
                <el-tag v-if="evalResult?.tokenConsumed" type="info" effect="plain">Token {{ evalResult?.tokenConsumed }}</el-tag>
                <span class="eval-sample-text">关系抽样 {{ evalResult?.sampledRelations }} 条 / 实体抽样 {{ evalResult?.sampledEntities }} 条</span>
              </div>
            </div>
            <div class="eval-panel-body">
              <div v-if="evaluating" class="eval-progress-row">
                <el-progress
                  :percentage="evalProgress && evalProgress.total ? Math.round(evalProgress.done / evalProgress.total * 100) : 0"
                  :stroke-width="14"
                  :status="evalProgress && evalProgress.done >= evalProgress.total ? 'success' : undefined"
                />
                <span class="eval-progress-text">
                  已评估指标 {{ evalProgress?.done ?? 0 }}/{{ evalProgress?.total ?? 0 }}
                  <template v-if="evalProgress?.current">· 最新完成：{{ evalProgress.current }}</template>
                </span>
              </div>
              <div class="eval-overview">
                <div class="eval-overall-score">
                  <div class="eval-score-num" :class="scoreClass(evalResult?.overall)">{{ formatScore(evalResult?.overall) }}</div>
                  <div class="eval-score-label">综合得分（LLM 裁判均值）</div>
                </div>
                <div v-if="evalRadarReady" ref="evalRadarRef" class="eval-radar"></div>
                <div class="eval-intrinsic-grid">
                  <div class="eval-stat" v-for="s in intrinsicStats" :key="s.label">
                    <div class="eval-stat-value">{{ s.value }}</div>
                    <div class="eval-stat-label">{{ s.label }}</div>
                  </div>
                </div>
              </div>
              <div v-if="isolatedList.length" class="eval-isolated">
                <span class="eval-isolated-label">孤立实体（{{ isolatedList.length }}）：</span>
                <el-tag
                  v-for="n in isolatedList.slice(0, 20)"
                  :key="n"
                  size="small"
                  type="warning"
                  effect="plain"
                  style="margin: 2px 4px 2px 0;"
                >{{ n }}</el-tag>
                <span v-if="isolatedList.length > 20" class="eval-isolated-more">等共 {{ isolatedList.length }} 个</span>
              </div>

              <h4 class="eval-section-title">LLM 裁判指标（G-Eval · 三级判定）</h4>
              <el-table :data="judgeRows" border>
                <el-table-column type="expand">
                  <template #default="{ row }">
                    <div class="eval-detail-list">
                      <div v-if="!row.details.length" class="eval-detail-empty">无明细数据</div>
                      <div v-for="(d, i) in row.details" :key="i" class="eval-detail-item is-clickable" @click="openDrill(row, d)">
                        <el-tag :type="detailVerdictType(d)" size="small" effect="dark">{{ detailVerdictText(d) }}</el-tag>
                        <span class="eval-detail-item-text">{{ formatDetailItem(row.key, d) }}</span>
                        <span v-if="d.reason" class="eval-detail-reason">{{ d.reason }}</span>
                      </div>
                      <div class="eval-detail-tip">点击任意样本可查看原文定位与高亮</div>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column prop="name" label="评估指标" min-width="150" />
                <el-table-column label="得分" width="200">
                  <template #default="{ row }">
                    <el-progress
                      v-if="row.score !== null && row.score !== undefined"
                      :percentage="Math.round(row.score * 100)"
                      :color="progressColor(row.score)"
                      :stroke-width="14"
                      :text-inside="true"
                    />
                    <span v-else class="eval-score-none">—</span>
                  </template>
                </el-table-column>
                <el-table-column prop="reason" label="整体结论" min-width="320">
                  <template #default="{ row }">
                    <span class="eval-reason-text">{{ row.reason || '-' }}</span>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </div>

          <!-- 评估历史记录 -->
          <div class="eval-panel">
            <div class="eval-panel-header">
              <span class="eval-panel-title"><span class="eval-bar"></span>评估历史记录</span>
              <div class="eval-header-extra">
                <el-button size="small" :icon="Refresh" @click="loadEvalRecords">刷新</el-button>
              </div>
            </div>
            <div class="eval-panel-body">
              <el-table :data="evalRecords" border v-loading="evalRecordsLoading" size="small">
                <el-table-column type="index" min-width="50" align="center" />
                <el-table-column prop="id" label="评估ID" min-width="150" align="center" />
                <el-table-column prop="taskId" label="抽取任务ID" min-width="150" align="center" />
                <el-table-column prop="sampleSize" label="抽样数量" min-width="90" align="center">
                  <template #default="{ row }">{{ row.sampleSize === 0 ? '全部' : `${row.sampleSize} 条` }}</template>
                </el-table-column>
                <el-table-column prop="overall" label="综合得分" min-width="90" align="center">
                  <template #default="{ row }">
                    <el-tag v-if="row.overall != null" :type="row.overall >= 0.8 ? 'success' : row.overall >= 0.6 ? 'warning' : 'danger'" size="small">
                      {{ (row.overall * 100).toFixed(1) }}
                    </el-tag>
                    <span v-else>—</span>
                  </template>
                </el-table-column>
                <el-table-column prop="tokenConsumed" label="Token" min-width="90" align="center">
                  <template #default="{ row }">{{ row.tokenConsumed ?? '—' }}</template>
                </el-table-column>
                <el-table-column prop="duration" label="耗时(ms)" min-width="90" align="center">
                  <template #default="{ row }">{{ row.duration ?? '—' }}</template>
                </el-table-column>
                <el-table-column prop="createTime" label="评估时间" min-width="150">
                  <template #default="{ row }">{{ formatTime(row.createTime) }}</template>
                </el-table-column>
                <el-table-column label="操作" min-width="180" align="center">
                  <template #default="{ row }">
                    <el-button size="small" @click="onLoadEvalRecord(row.id)">查看</el-button>
                    <el-button size="small" @click="openCompareDialog(row)">对比</el-button>
                    <el-button size="small" type="danger" @click="deleteEvalRecord(row.id)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
              <div class="ext-pagination">
                <el-pagination v-model:current-page="evalRecordsPage" :page-size="evalRecordsSize" :total="evalRecordsTotal" layout="total, prev, pager, next" @current-change="loadEvalRecords" />
              </div>
            </div>
          </div>

          <!-- 对比记录选择对话框 -->
          <el-dialog v-model="compareVisible" title="选择要对比的评估记录" width="680px" append-to-body>
            <div class="compare-dialog-tip">请勾选 2~3 条评估记录（A 为基准，其余为对比对象）</div>
            <el-table
              ref="compareTableRef"
              :data="evalRecords"
              border
              size="small"
              max-height="360"
              @selection-change="onCompareSelectionChange"
            >
              <el-table-column type="selection" width="45" :selectable="isSelectable" />
              <el-table-column prop="id" label="评估ID" min-width="150" align="center" />
              <el-table-column prop="taskId" label="抽取任务ID" min-width="150" align="center" />
              <el-table-column prop="sampleSize" label="抽样数量" min-width="85" align="center">
                <template #default="{ row }">{{ row.sampleSize === 0 ? '全部' : `${row.sampleSize} 条` }}</template>
              </el-table-column>
              <el-table-column prop="overall" label="综合得分" min-width="85" align="center">
                <template #default="{ row }">
                  <span v-if="row.overall != null">{{ (row.overall * 100).toFixed(1) }}</span>
                  <span v-else>—</span>
                </template>
              </el-table-column>
              <el-table-column prop="createTime" label="评估时间" min-width="150">
                <template #default="{ row }">{{ formatTime(row.createTime) }}</template>
              </el-table-column>
            </el-table>
            <template #footer>
              <el-button @click="compareVisible = false">取消</el-button>
              <el-button type="primary" :disabled="compareSelection.length < 2 || compareSelection.length > 3" :loading="comparing" @click="confirmCompare">确定对比</el-button>
            </template>
          </el-dialog>

          <!-- 评估对比结果大弹窗（最多三份完整报告 · 优势高亮） -->
          <el-dialog v-model="compareResultVisible" title="评估对比" width="1400px" top="3vh" append-to-body class="compare-result-dialog">
            <div class="cmp-toolbar">
              <el-switch v-model="highlightAdvantage" active-text="高亮优势项" />
            </div>
            <div v-if="cmpRadarKeys.length >= 3" ref="cmpRadarRef" class="cmp-radar"></div>
            <div class="cmp-reports" :class="`is-${compareRecords.length}`" v-loading="comparing">
              <div
                v-for="(rec, si) in compareRecords"
                :key="rec.id"
                class="cmp-report"
                :class="{ 'is-winner': highlightAdvantage && overallWinnerIdx === si }"
              >
                <div class="cmp-report-head">
                  <el-tag :type="si === 0 ? 'warning' : 'primary'" effect="plain">{{ si === 0 ? 'A · 基准' : `${String.fromCharCode(65 + si)} · 对比` }}</el-tag>
                  <span class="cmp-report-id">评估 #{{ compareRecords[si]?.id }}</span>
                  <span class="cmp-report-meta">
                    {{ compareRecords[si]?.sampleSize === 0 ? '全部' : (compareRecords[si]?.sampleSize + ' 条') }} · {{ formatTime(compareRecords[si]?.createTime) }}
                  </span>
                </div>
                <div class="cmp-report-body">
                  <div class="eval-overview">
                    <div class="eval-overall-score">
                      <div class="eval-score-num" :class="scoreClass(compareResults?.[si]?.overall)">{{ formatScore(compareResults?.[si]?.overall) }}</div>
                      <div class="eval-score-label">综合得分（LLM 裁判均值）</div>
                    </div>
                    <div class="eval-intrinsic-grid">
                      <div
                        class="eval-stat"
                        v-for="s in cmpIntrinsicStats(si)"
                        :key="s.label"
                        :class="{ 'is-adv': highlightAdvantage && s.winner === si }"
                      >
                        <div class="eval-stat-value">{{ s.value }}</div>
                        <div class="eval-stat-label">{{ s.label }}</div>
                      </div>
                    </div>
                  </div>

                  <h4 class="eval-section-title">LLM 裁判指标（G-Eval）</h4>
                  <el-table :data="cmpJudgeRows(si)" border size="small">
                    <el-table-column prop="name" label="评估指标" min-width="120" />
                    <el-table-column label="得分" width="180">
                      <template #default="{ row }">
                        <el-progress
                          v-if="row.score !== null && row.score !== undefined"
                          :percentage="Math.round(row.score * 100)"
                          :color="progressColor(row.score)"
                          :stroke-width="14"
                          :text-inside="true"
                        />
                        <span v-else class="eval-score-none">—</span>
                      </template>
                    </el-table-column>
                    <el-table-column label="" width="70" align="center">
                      <template #default="{ row }">
                        <el-tag
                          v-if="highlightAdvantage && row.winner === si"
                          type="success" size="small" effect="dark" round
                        >优</el-tag>
                      </template>
                    </el-table-column>
                  </el-table>
                </div>
              </div>
            </div>
          </el-dialog>

          <!-- 失败样本下钻弹窗（原文定位 + 实体/证据高亮） -->
          <el-dialog v-model="drillVisible" :title="`样本详情 · ${drillData?.metricName || ''}`" width="760px" append-to-body>
            <div v-if="drillData" class="drill-body">
              <div class="drill-sample">
                <el-tag :type="detailVerdictType(drillData.detail)" size="small" effect="dark">
                  {{ detailVerdictText(drillData.detail) }}
                </el-tag>
                <span class="drill-sample-text">{{ formatDetailItem(drillData.metricKey, drillData.detail) }}</span>
              </div>
              <div v-if="drillData.detail.reason" class="drill-reason">
                <span class="drill-reason-label">裁判理由：</span>{{ drillData.detail.reason }}
              </div>
              <div class="drill-text-label">原文（高亮为样本涉及实体/证据）</div>
              <div class="drill-text" v-html="drillHtml"></div>
            </div>
          </el-dialog>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { projectApi, modelApi, corpusApi, extractionApi, entityTypeApi, relationTypeApi } from '@/api'
import { exportExtractionTask } from '@/utils/export'
import ExtractionLayout from '@/components/ExtractionLayout.vue'

interface Project { id: number; projectName: string }
interface ModelInfo { id: number; modelName: string }
interface Corpus { id: number; title: string; content?: string; source?: string; projectId?: number | string }
interface ExtractEntity { name: string; type: string; properties?: Record<string, any> }
interface ExtractRelation {
  head: string; relation: string; tail: string; properties?: Record<string, any>
  status?: string; confidence?: number; vt_from?: string; vt_to?: string
  subjectType?: string; objectType?: string
  evidenceSpans?: { start: number; end: number }[]
}
interface ExtractResult {
  entities: ExtractEntity[]
  relations: ExtractRelation[]
  costTime?: number
  inputText?: string
  text?: string
}

const projects = ref<Project[]>([])
const models = ref<ModelInfo[]>([])
const corpusList = ref<Corpus[]>([])
const projectId = ref<number | undefined>()
const modelId = ref<number | undefined>()
const corpusId = ref<number | undefined>()
const corpusMode = ref<'corpus' | 'manual'>('manual')
const inputText = ref('')
const extracting = ref(false)
const result = ref<ExtractResult | null>(null)
const stepActive = ref(0)

// 抽取模型选择（llm_model 表，enabled=1，逻辑删除过滤）
interface ExtractLlmModel { id: number; displayName: string; modelName: string }
const extractLlmModels = ref<ExtractLlmModel[]>([])
const extractLlmModelId = ref<number | undefined>()
const extractLlmLoading = ref(false)

async function loadExtractLlmModels() {
  extractLlmLoading.value = true
  try {
    const res = await fetch('/api/v1/chat/llm-models', { credentials: 'include' })
    if (!res.ok) throw new Error('HTTP ' + res.status)
    const json = await res.json()
    const raw = Array.isArray(json) ? json : (json?.data ?? [])
    const list: ExtractLlmModel[] = (Array.isArray(raw) ? raw : []) as ExtractLlmModel[]
    if (list.length) {
      extractLlmModels.value = list
      const saved = Number(localStorage.getItem('kg_extract_llm_model_id') || '')
      const fallback = list.find(m => m.modelName === 'deepseek-chat')?.id || list[0].id
      extractLlmModelId.value = list.some(m => m.id === saved) ? saved : fallback
    }
  } catch {
    extractLlmModels.value = []
  } finally {
    extractLlmLoading.value = false
  }
}

watch(extractLlmModelId, (v) => {
  if (v) localStorage.setItem('kg_extract_llm_model_id', String(v))
})

// 实体关系配置
const activeConfigTab = ref('extract')
const modelEntityTypes = ref<string[]>([])
const modelRelationTypes = ref<string[]>([])
const customEntityTypes = ref<string[]>([])
const customRelationTypes = ref<string[]>([])
const newEntityType = ref('')
const newRelationType = ref('')

const history = ref<any[]>([])
const historyLoading = ref(false)
const histPage = ref(1)
const histSize = ref(10)
const histTotal = ref(0)

const PALETTE = ['#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#909399', '#9c27b0', '#00bcd4', '#ff9800']
const typeColorMap = computed(() => {
  const map: Record<string, string> = {}
  const types = new Set((result.value?.entities || []).map((e) => e.type))
  Array.from(types).forEach((t, i) => {
    map[t] = PALETTE[i % PALETTE.length]
  })
  return map
})

const entities = computed(() => result.value?.entities || [])
const relations = computed(() => result.value?.relations || [])

// 结果列表分页（替代原 max-height 滚动）
const ENTITY_PAGE_SIZE = 20
const REL_PAGE_SIZE = 20
const entityPage = ref(1)
const relPage = ref(1)
const pagedEntities = computed(() => {
  const start = (entityPage.value - 1) * ENTITY_PAGE_SIZE
  return entities.value.slice(start, start + ENTITY_PAGE_SIZE)
})
const pagedRelations = computed(() => {
  const start = (relPage.value - 1) * REL_PAGE_SIZE
  return relations.value.slice(start, start + REL_PAGE_SIZE)
})
watch(entities, () => { entityPage.value = 1 })
watch(relations, () => { relPage.value = 1 })

const canExtract = computed(() => {
  if (!modelId.value) return false
  if (corpusMode.value === 'corpus') return !!corpusId.value
  return !!inputText.value.trim()
})

const highlightedText = computed(() => {
  if (!result.value) return ''
  const text = result.value.inputText || result.value.text || inputText.value
  if (!text) return ''
  let html = escapeHtml(text)
  const ents = result.value.entities || []
  const sorted = [...ents].sort((a, b) => b.name.length - a.name.length)
  for (const e of sorted) {
    if (!e.name) continue
    const color = typeColorMap.value[e.type] || '#409eff'
    const re = new RegExp(escapeReg(e.name), 'g')
    html = html.replace(re, `<span class="hl-entity" style="background:${color}33;color:${color};border:1px solid ${color};border-radius:3px;padding:0 2px">${escapeHtml(e.name)}</span>`)
  }
  return html
})

/** 兜底从分页响应里提取 records，兼容不同后端返回结构 */
function extractRecords(res: any): any[] {
  if (!res) return []
  const payload = res.data ?? res
  if (Array.isArray(payload)) return payload
  if (payload && Array.isArray(payload.records)) return payload.records
  if (payload && Array.isArray(payload.list)) return payload.list
  if (payload && typeof payload === 'object') {
    const arrVal = Object.values(payload).find(v => Array.isArray(v))
    if (arrVal) return arrVal as any[]
  }
  return []
}

async function loadProjects() {
  const res = await projectApi.list({ pageNum: 1, pageSize: 100 })
  projects.value = extractRecords(res).slice().reverse()
  if (projects.value.length > 0 && !projectId.value) {
    projectId.value = projects.value[0].id
    await onProjectChange()
  }
}

async function loadCorpusList() {
  // 始终拉取全部语料（不按项目过滤），确保"语料管理"中的语料都能在选择列表中看到
  try {
    const cRes = await corpusApi.list({ pageNum: 1, pageSize: 500 })
    corpusList.value = extractRecords(cRes)
  } catch {
    corpusList.value = []
  }
}

function projectNameById(pid: any): string {
  if (!pid) return ''
  const p = projects.value.find((x) => x.id === pid || String(x.id) === String(pid))
  return p?.projectName || ''
}

async function onProjectChange() {
  models.value = []
  corpusList.value = []
  modelId.value = undefined
  corpusId.value = undefined
  inputText.value = ''
  if (!projectId.value) {
    await loadCorpusList()
    return
  }
  const [mRes] = await Promise.all([
    modelApi.list(projectId.value),
    loadCorpusList(),
  ])
  models.value = extractRecords(mRes)
  // 自动选择第一个模型并加载本体
  if (models.value.length > 0) {
    modelId.value = models.value[0].id
    await onModelChange()
  }
}

async function loadCorpusContent(id: number | undefined) {
  if (!id) {
    inputText.value = ''
    return
  }
  try {
    const res = await corpusApi.get(id)
    inputText.value = (res.data as Corpus)?.content || ''
  } catch {
    const found = corpusList.value.find(c => c.id === id)
    inputText.value = found?.content || ''
  }
}

async function onCorpusModeChange(mode: 'corpus' | 'manual') {
  corpusMode.value = mode
  if (mode === 'manual') {
    corpusId.value = undefined
  } else {
    // 每次切到语料选择 tab 都强制刷新，避免切项目/回来后无数据
    await loadCorpusList()
  }
}

async function onModelChange() {
  modelEntityTypes.value = []
  modelRelationTypes.value = []
  customEntityTypes.value = []
  customRelationTypes.value = []
  if (!modelId.value) return
  try {
    const [eRes, rRes] = await Promise.all([
      entityTypeApi.list(modelId.value),
      relationTypeApi.list(modelId.value)
    ])
    modelEntityTypes.value = (eRes.data || []).map((e: any) => e.entityName).filter(Boolean)
    modelRelationTypes.value = (rRes.data || []).map((r: any) => r.relationName).filter(Boolean)
  } catch {
    // 加载失败忽略
  }
}

function addEntityType() {
  const name = newEntityType.value.trim()
  if (!name) return
  if (modelEntityTypes.value.includes(name) || customEntityTypes.value.includes(name)) {
    ElMessage.warning('该实体类型已存在')
    return
  }
  customEntityTypes.value.push(name)
  newEntityType.value = ''
}

function addRelationType() {
  const name = newRelationType.value.trim()
  if (!name) return
  if (modelRelationTypes.value.includes(name) || customRelationTypes.value.includes(name)) {
    ElMessage.warning('该关系类型已存在')
    return
  }
  customRelationTypes.value.push(name)
  newRelationType.value = ''
}

function removeModelEntity(name: string) {
  modelEntityTypes.value = modelEntityTypes.value.filter(t => t !== name)
}

function removeModelRelation(name: string) {
  modelRelationTypes.value = modelRelationTypes.value.filter(t => t !== name)
}

function clearOntologyConfig() {
  customEntityTypes.value = []
  customRelationTypes.value = []
  newEntityType.value = ''
  newRelationType.value = ''
}

function getEffectiveEntityTypes(): string[] | undefined {
  const all = [...modelEntityTypes.value, ...customEntityTypes.value]
  return all.length > 0 ? all : undefined
}

function getEffectiveRelationTypes(): string[] | undefined {
  const all = [...modelRelationTypes.value, ...customRelationTypes.value]
  return all.length > 0 ? all : undefined
}

function parseResult(data: any): ExtractResult | null {
  if (!data) return null
  if (data.entities) return data as ExtractResult
  if (data.result && typeof data.result === 'string') {
    try {
      const parsed = JSON.parse(data.result)
      return {
        entities: parsed.entities || [],
        relations: parsed.relations || [],
        costTime: parsed.duration || data.duration,
        inputText: data.inputText,
      }
    } catch {
      return null
    }
  }
  return null
}

async function handleExtract() {
  if (!modelId.value) {
    ElMessage.warning('请选择图谱模型')
    return
  }
  extracting.value = true
  stepActive.value = 2
  try {
    const res = await extractionApi.llm({
      projectId: projectId.value,
      modelId: modelId.value,
      corpusId: corpusMode.value === 'corpus' ? corpusId.value : undefined,
      inputText: corpusMode.value === 'manual' ? inputText.value : undefined,
      mode: 'zero_shot',
      customEntityTypes: getEffectiveEntityTypes(),
      customRelationTypes: getEffectiveRelationTypes(),
      llmModelId: extractLlmModelId.value
    })
    result.value = parseResult(res.data)
    stepActive.value = 4
    ElMessage.success('抽取完成')
    await loadHistory()
  } catch {
    stepActive.value = 0
  } finally {
    extracting.value = false
  }
}

async function loadHistory() {
  historyLoading.value = true
  try {
    const res = await extractionApi.list({
      extractionType: 'LLM',
      pageNum: histPage.value,
      pageSize: histSize.value,
      sortField: 'createTime',
      sortOrder: 'descend',
    })
    history.value = res.data?.records || res.data || []
    histTotal.value = Number(res.data?.total) || history.value.length
  } finally {
    historyLoading.value = false
  }
}

async function viewHistory(row: any) {
  const res = await extractionApi.get(row.id)
  result.value = parseResult(res.data)
  currentHistoryId.value = row.id
  stepActive.value = 4
}

const currentHistoryId = ref<number | null>(null)

async function deleteHistory(row: any) {
  try {
    await ElMessageBox.confirm('确定删除该条抽取记录吗？删除后不可恢复。', '删除确认', { type: 'warning' })
  } catch {
    return
  }
  try {
    await extractionApi.delete(row.id)
    ElMessage.success('删除成功')
    // 若删除的正是当前展示的结果，清空结果
    if (currentHistoryId.value === row.id) {
      result.value = null
      currentHistoryId.value = null
      stepActive.value = 0
    }
    loadHistory()
  } catch {
    // request 层已提示
  }
}

function statusType(status: number): string {
  return { 1: 'warning', 2: 'success', 3: 'danger' }[status] || 'info'
}
function statusText(status: number): string {
  return { 1: '进行中', 2: '成功', 3: '失败' }[status] || '未知'
}
function extractionTypeColor(type: string): string {
  if (type === 'DL') return 'danger'
  if (type === 'KOS') return 'success'
  if (type === 'STRUCTURE') return 'warning'
  return 'primary'
}
function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}
function escapeReg(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}
function formatTime(t?: string): string {
  if (!t) return '-'
  return t.replace('T', ' ').substring(0, 19)
}


// ==================== 质量评估（G-Eval 风格 LLM-as-Judge） ====================
const pageTab = ref('extract')
const evaluating = ref(false)
const evalSampleSize = ref(30)

// 可选评估指标（与 Python evaluation.py 的裁判指标一一对应）
const EVAL_METRICS = [
  { key: 'tripleFaithfulness', name: '三元组忠实度' },
  { key: 'predicateReasonableness', name: '谓词合理性' },
  { key: 'bitemporalCorrectness', name: '双时态正确性' },
  { key: 'evidenceValidity', name: '证据句有效性' },
  { key: 'entityCorrectness', name: '实体边界正确性' },
] as const
type EvalMetricKey = (typeof EVAL_METRICS)[number]['key']

const evalMetrics = ref<Record<EvalMetricKey, boolean>>({
  tripleFaithfulness: true,
  predicateReasonableness: true,
  bitemporalCorrectness: true,
  evidenceValidity: true,
  entityCorrectness: true,
})

const selectedMetricKeys = computed(() => EVAL_METRICS.filter(m => evalMetrics.value[m.key]).map(m => m.key))
const isAllMetricsSelected = computed(() => selectedMetricKeys.value.length === EVAL_METRICS.length)

function toggleAllMetrics() {
  const target = !isAllMetricsSelected.value
  EVAL_METRICS.forEach(m => { evalMetrics.value[m.key] = target })
}

// 裁判模型选择（llm_model 表，enabled=1，逻辑删除过滤）
interface EvalLlmModel { id: number; displayName: string; modelName: string }
const evalLlmModels = ref<EvalLlmModel[]>([])
const evalLlmModelId = ref<number | undefined>()
const evalLlmLoading = ref(false)

async function loadEvalLlmModels() {
  evalLlmLoading.value = true
  try {
    const res = await fetch('/api/v1/chat/llm-models', { credentials: 'include' })
    if (!res.ok) throw new Error('HTTP ' + res.status)
    const json = await res.json()
    const raw = Array.isArray(json) ? json : (json?.data ?? [])
    const list: EvalLlmModel[] = (Array.isArray(raw) ? raw : []) as EvalLlmModel[]
    if (list.length) {
      evalLlmModels.value = list
      const saved = Number(localStorage.getItem('kg_llm_model_id') || '')
      const fallback = list.find(m => m.modelName === 'deepseek-chat')?.id || list[0].id
      evalLlmModelId.value = list.some(m => m.id === saved) ? saved : fallback
    }
  } catch (e) {
    evalLlmModels.value = []
    console.warn('[KGraph] 评估裁判模型清单加载失败:', e)
  } finally {
    evalLlmLoading.value = false
  }
}

// 评估配置：选择抽取任务 + 评估语料即可评估，无需先抽取
const evalHistory = ref<any[]>([])
const evalHistLoading = ref(false)
const evalTaskId = ref<number | undefined>()
const evalData = ref<ExtractResult | null>(null)

/** 评估目标：已选抽取任务的数据 */
const evalTarget = computed<ExtractResult | null>(() => evalData.value)

// 评估原文：默认自动带入（任务原文/当前输入），支持选择语料或手动指定覆盖
const evalTextOverride = ref('')
const evalTextOverrideFrom = ref<'corpus' | 'manual'>('manual')
const evalCorpusVisible = ref(false)
const evalCorpusPickId = ref<number | undefined>()
const evalManualVisible = ref(false)
const evalManualText = ref('')

/** 实际使用的评估语料原文（覆盖优先，其次任务自动带入） */
const evalTextUsed = computed(() => {
  if (evalTextOverride.value) return evalTextOverride.value
  const target = evalTarget.value
  return target?.inputText || target?.text || ''
})

const evalCorpusPickPreview = computed(() => {
  const c = corpusList.value.find(x => x.id === evalCorpusPickId.value)
  const content = c?.content || ''
  return content ? `${content.slice(0, 120)}${content.length > 120 ? '…' : ''}` : ''
})

function openCorpusPick() {
  evalCorpusPickId.value = undefined
  evalCorpusVisible.value = true
}

function confirmCorpusPick() {
  const c = corpusList.value.find(x => x.id === evalCorpusPickId.value)
  if (c?.content) {
    evalTextOverride.value = c.content
    evalTextOverrideFrom.value = 'corpus'
    evalCorpusVisible.value = false
    ElMessage.success(`已使用语料「${c.title}」原文（${c.content.length} 字）`)
  } else {
    ElMessage.warning('该语料无内容')
  }
}

function confirmManualText() {
  evalTextOverride.value = evalManualText.value.trim()
  evalTextOverrideFrom.value = 'manual'
  evalManualVisible.value = false
}

function clearEvalTextOverride() {
  evalTextOverride.value = ''
  evalManualText.value = ''
}

async function loadEvalHistory() {
  evalHistLoading.value = true
  try {
    const res = await extractionApi.list({
      pageNum: 1,
      pageSize: 50,
      sortField: 'createTime',
      sortOrder: 'descend',
    })
    evalHistory.value = res.data?.records || res.data || []
  } finally {
    evalHistLoading.value = false
  }
}

async function onEvalTaskChange(id: number | undefined) {
  evalData.value = null
  evalResult.value = null
  evalRecords.value = []
  evalRecordsTotal.value = 0
  evalRecordsPage.value = 1
  if (!id) return
  evalTextOverride.value = ''
  evalManualText.value = ''
  loadEvalRecords()
  try {
    const res = await extractionApi.get(id)
    evalData.value = parseResult(res.data)
    if (!evalData.value) {
      ElMessage.warning('该任务结果解析失败，请换一条')
      return
    }
    // 语料库抽取的任务不存 inputText，按 corpusId 自动加载原文
    if (!evalData.value.inputText && (res.data as any)?.corpusId) {
      try {
        const c = await corpusApi.get((res.data as any).corpusId)
        evalData.value.inputText = (c.data as Corpus)?.content || ''
      } catch {
        // 加载失败时保留为空，用户可手动选择原文
      }
    }
  } catch {
    // request 层已提示
  }
}

interface EvalResult {
  intrinsic: {
    entityCount: number
    relationCount: number
    isolatedEntities: string[]
    isolatedRate: number
    avgDegree: number
    evidenceCoverage: number
    lowConfidenceRate: number | null
  }
  llmJudge: Record<string, { score: number | null; reason: string; details: any[] }>
  overall: number | null
  sampledRelations: number
  sampledEntities: number
  tokenConsumed?: number
  judgeModel?: string
  duration?: number
  evaluationId?: number
  evalCreateTime?: number | null
}
const evalResult = ref<EvalResult | null>(null)

// ==================== 评估历史（持久化，切换任务/刷新页面后可回看） ====================
interface EvalRecord {
  id: number
  taskId: number
  sampleSize: number
  overall: number | null
  tokenConsumed: number | null
  duration: number | null
  createTime: string
}
const evalRecords = ref<EvalRecord[]>([])
const evalRecordsLoading = ref(false)
const evalRecordsPage = ref(1)
const evalRecordsSize = 10
const evalRecordsTotal = ref(0)

async function loadEvalRecords() {
  evalRecordsLoading.value = true
  try {
    const res = await extractionApi.evaluationList(undefined, {
      pageNum: evalRecordsPage.value,
      pageSize: evalRecordsSize,
      sortField: 'createTime',
      sortOrder: 'descend',
    })
    evalRecords.value = res.data?.records || []
    evalRecordsTotal.value = Number(res.data?.total || 0)
  } catch {
    // request 层已提示
  } finally {
    evalRecordsLoading.value = false
  }
}

async function onLoadEvalRecord(id: number) {
  try {
    const res = await extractionApi.evaluationGet(id)
    evalResult.value = res.data
  } catch {
    // request 层已提示
  }
}

// ==================== 评估对比（对话框选择 2~3 条历史记录 · 多路报告对照） ====================
const MAX_COMPARE = 3
const compareVisible = ref(false)
const compareResultVisible = ref(false)
const compareSelection = ref<EvalRecord[]>([])
const compareRecords = ref<EvalRecord[]>([])
const compareResults = ref<EvalResult[] | null>(null)
const comparing = ref(false)
const compareTableRef = ref()
const highlightAdvantage = ref(true)

function isSelectable(_row: EvalRecord): boolean {
  // 已选满 3 条时其余行不可再勾选（已勾选的仍可取消）
  return true
}

function onCompareSelectionChange(rows: EvalRecord[]) {
  // 超过 3 条时保留前 3 条（element-plus 多选无硬上限，这里手动截断）
  if (rows.length > MAX_COMPARE) {
    const kept = rows.slice(0, MAX_COMPARE)
    compareSelection.value = kept
    nextTick(() => {
      if (compareTableRef.value) {
        compareTableRef.value.clearSelection()
        kept.forEach(r => compareTableRef.value.toggleRowSelection(r, true))
      }
    })
    ElMessage.warning(`最多支持 ${MAX_COMPARE} 条记录同时对比`)
    return
  }
  compareSelection.value = rows
}

function openCompareDialog(row: EvalRecord) {
  compareVisible.value = true
  // 打开对话框后默认勾选当前行（作为基准 A）
  nextTick(() => {
    if (compareTableRef.value && row) {
      compareTableRef.value.clearSelection()
      compareTableRef.value.toggleRowSelection(row, true)
    }
  })
}

async function confirmCompare() {
  const sel = compareSelection.value
  if (sel.length < 2) {
    ElMessage.warning('请至少勾选两条评估记录')
    return
  }
  comparing.value = true
  try {
    const rs = await Promise.all(sel.map(r => extractionApi.evaluationGet(r.id)))
    compareRecords.value = [...sel]
    compareResults.value = rs.map(r => r.data)
    compareVisible.value = false
    compareResultVisible.value = true
  } catch {
    // request 层已提示
  } finally {
    comparing.value = false
  }
}

function clearCompare() {
  compareRecords.value = []
  compareResults.value = null
  compareResultVisible.value = false
}

// 优势判定：返回最优记录的下标（higherBetter=false 时低者优；全空或并列返回 null）
function cmpWinnerIdx(
  values: Array<number | null | undefined>, higherBetter: boolean,
): number | null {
  const valid = values.map((v, i) => [v, i] as const).filter((p): p is [number, number] => p[0] != null)
  if (valid.length === 0) return null
  let best = valid[0]
  let tie = false
  for (let k = 1; k < valid.length; k++) {
    const [v] = valid[k]
    const better = higherBetter ? v! > best[0]! : v! < best[0]!
    if (better) {
      best = valid[k]
      tie = false
    } else if (v === best[0]) {
      tie = true
    }
  }
  return tie ? null : best[1]
}

const overallWinnerIdx = computed<number | null>(() => {
  const rs = compareResults.value
  if (!rs || rs.length === 0) return null
  return cmpWinnerIdx(rs.map(r => r.overall), true)
})

// 内在指标定义（key 取自 intrinsic 字段，反向指标标注）
const CMP_INTRINSIC_DEFS: Array<{ key: string; label: string; higherBetter: boolean }> = [
  { key: 'entityCount', label: '实体总数', higherBetter: true },
  { key: 'relationCount', label: '关系总数', higherBetter: true },
  { key: 'avgDegree', label: '平均度', higherBetter: true },
  { key: 'isolatedRate', label: '孤立实体率', higherBetter: false },
  { key: 'evidenceCoverage', label: '证据覆盖率', higherBetter: true },
  { key: 'lowConfidenceRate', label: '低置信率(<0.6)', higherBetter: false },
]

function cmpIntrinsicStats(si: number): Array<{ label: string; value: string; winner: number | null }> {
  const rs = compareResults.value
  if (!rs || !rs[si]) return []
  const ins = rs[si].intrinsic
  if (!ins) return []
  const pct = (v: number | null | undefined) => (v === null || v === undefined ? '-' : `${(v * 100).toFixed(1)}%`)
  return CMP_INTRINSIC_DEFS.map(d => {
    const values = rs.map(r => (r.intrinsic as any)?.[d.key] ?? null)
    const v = values[si]
    const value = d.key === 'entityCount' || d.key === 'relationCount' || d.key === 'avgDegree'
      ? (v == null ? '-' : String(v))
      : pct(v)
    return { label: d.label, value, winner: cmpWinnerIdx(values, d.higherBetter) }
  })
}

function cmpJudgeRows(si: number): Array<{ key: string; name: string; score: number | null; winner: number | null }> {
  const rs = compareResults.value
  if (!rs || !rs[si]) return []
  const own = rs[si].llmJudge
  if (!own) return []
  return Object.entries(own).map(([key, v]) => {
    const values = rs.map(r => (r.llmJudge as any)?.[key]?.score ?? null)
    return { key, name: JUDGE_METRIC_NAMES[key] || key, score: v?.score ?? null, winner: cmpWinnerIdx(values, true) }
  })
}

async function deleteEvalRecord(id: number) {
  try {
    await ElMessageBox.confirm('确定删除该条评估历史吗？删除后不可恢复。', '删除确认', { type: 'warning' })
  } catch {
    return
  }
  try {
    await extractionApi.evaluationDelete(id)
    ElMessage.success('删除成功')
    // 若删除的正是当前展示的报告，清空报告
    if (evalResult.value?.evaluationId === id) evalResult.value = null
    // 若删除的记录在对比结果里，清空对比
    if (compareRecords.value.some(r => r.id === id)) clearCompare()
    loadEvalRecords()
  } catch {
    // request 层已提示
  }
}

const JUDGE_METRIC_NAMES: Record<string, string> = {
  tripleFaithfulness: '三元组忠实度',
  predicateReasonableness: '谓词合理性',
  bitemporalCorrectness: '双时态标注正确性',
  evidenceValidity: '证据句有效性',
  entityCorrectness: '实体边界正确性',
}

const judgeRows = computed(() => {
  if (!evalResult.value?.llmJudge) return []
  return Object.entries(evalResult.value.llmJudge).map(([key, v]) => ({
    key,
    name: JUDGE_METRIC_NAMES[key] || key,
    score: v.score,
    reason: v.reason,
    details: v.details || [],
  }))
})

const intrinsicStats = computed(() => {
  const ins = evalResult.value?.intrinsic
  if (!ins) return []
  const pct = (v: number | null | undefined) => (v === null || v === undefined ? '-' : `${(v * 100).toFixed(1)}%`)
  return [
    { label: '实体总数', value: ins.entityCount },
    { label: '关系总数', value: ins.relationCount },
    { label: '平均度', value: ins.avgDegree },
    { label: '孤立实体率', value: pct(ins.isolatedRate) },
    { label: '证据覆盖率', value: pct(ins.evidenceCoverage) },
    { label: '低置信率(<0.6)', value: pct(ins.lowConfidenceRate) },
  ]
})

const isolatedList = computed(() => evalResult.value?.intrinsic?.isolatedEntities || [])

function scoreClass(score: number | null | undefined): string {
  if (score === null || score === undefined) return ''
  if (score >= 0.8) return 'is-good'
  if (score >= 0.6) return 'is-mid'
  return 'is-bad'
}

function formatScore(score: number | null | undefined): string {
  if (score === null || score === undefined) return '—'
  return (score * 100).toFixed(1)
}

function progressColor(score: number): string {
  if (score >= 0.8) return '#67c23a'
  if (score >= 0.6) return '#e6a23c'
  return '#f56c6c'
}

function formatDetailItem(key: string, d: any): string {
  if (key === 'entityCorrectness') return `${d.name}（${d.type}）`
  const parts = [`${d.head} → ${d.predicate} → ${d.tail}`]
  if (key === 'bitemporalCorrectness' && d.status) {
    const vt = [d.vt_from, d.vt_to].filter(Boolean).join('~')
    parts.push(`[${d.status}${vt ? ' ' + vt : ''}]`)
  }
  if (key === 'evidenceValidity' && d.evidence) parts.push(`证据：「${d.evidence}」`)
  return parts.join(' ')
}

// ==================== 三级判定（2=完全通过 / 1=部分正确 / 0=未通过） ====================
/** 兼容旧数据：无 verdict 时按 pass 布尔推断（true→2 / false→0） */
function detailVerdict(d: any): number {
  if (d?.verdict != null) return Number(d.verdict)
  return d?.pass ? 2 : 0
}

function detailVerdictText(d: any): string {
  const v = detailVerdict(d)
  return v === 2 ? '通过' : v === 1 ? '部分正确' : '未通过'
}

function detailVerdictType(d: any): 'success' | 'warning' | 'danger' {
  const v = detailVerdict(d)
  return v === 2 ? 'success' : v === 1 ? 'warning' : 'danger'
}

// ==================== 失败样本下钻（原文定位 + 证据高亮） ====================
const drillVisible = ref(false)
const drillData = ref<{ metricName: string; metricKey: string; detail: any } | null>(null)

function openDrill(row: any, d: any) {
  drillData.value = { metricName: row.name, metricKey: row.key, detail: d }
  drillVisible.value = true
}

/** 下钻弹窗原文 HTML：高亮样本中的实体名/证据片段出现位置 */
const drillHtml = computed(() => {
  const d = drillData.value?.detail
  const text = evalTextUsed.value
  if (!d || !text) return ''
  const kws = [d.head, d.tail, d.name, d.evidence]
    .filter((k): k is string => Boolean(k) && String(k).length > 1)
    .map(String)
  const uniq = [...new Set(kws)].sort((a, b) => b.length - a.length)
  let html = escapeHtml(text)
  for (const kw of uniq) {
    const esc = escapeReg(escapeHtml(kw))
    html = html.replace(new RegExp(esc, 'g'), (m) => `<mark>${m}</mark>`)
  }
  return html
})

// ==================== 评估雷达图（单报告 + 对比重叠） ====================
const evalRadarRef = ref<HTMLElement>()
let evalRadarChart: echarts.ECharts | null = null

/** 雷达图至少 3 个已出分指标才有意义 */
const evalRadarReady = computed(
  () => judgeRows.value.filter(r => r.score !== null && r.score !== undefined).length >= 3,
)

function renderEvalRadar() {
  if (!evalRadarReady.value || !evalRadarRef.value) return
  if (!evalRadarChart) evalRadarChart = echarts.init(evalRadarRef.value)
  const rows = judgeRows.value.filter(r => r.score !== null && r.score !== undefined)
  evalRadarChart.setOption(
    {
      radar: {
        indicator: rows.map(r => ({ name: r.name, max: 1 })),
        radius: '62%',
        axisName: { color: '#6b7280', fontSize: 11 },
        splitArea: { areaStyle: { color: ['#ffffff', '#f7f9fc'] } },
      },
      series: [
        {
          type: 'radar',
          areaStyle: { opacity: 0.25, color: '#165dff' },
          lineStyle: { color: '#165dff', width: 2 },
          itemStyle: { color: '#165dff' },
          data: [{ value: rows.map(r => r.score), name: '本次评估' }],
        },
      ],
    },
    { notMerge: true },
  )
}

watch(
  () => judgeRows.value.map(r => r.score).join(','),
  () => nextTick(renderEvalRadar),
)

// 对比弹窗重叠雷达图（A/B/C 三组同图）
const cmpRadarRef = ref<HTMLElement>()
let cmpRadarChart: echarts.ECharts | null = null

const CMP_RADAR_COLORS = ['#165dff', '#e6a23c', '#67c23a']

/** 对比记录的公共已出分指标（交集 >= 3 才渲染雷达图） */
const cmpRadarKeys = computed<string[]>(() => {
  const rs = compareResults.value
  if (!rs || rs.length < 2) return []
  let keys = new Set(Object.keys(rs[0]?.llmJudge || {}))
  for (const r of rs.slice(1)) {
    keys = new Set([...keys].filter(k => (r.llmJudge as any)?.[k]?.score != null))
  }
  return [...keys].filter(k => (rs[0].llmJudge as any)?.[k]?.score != null)
})

function renderCmpRadar() {
  const rs = compareResults.value
  if (!rs || rs.length < 2 || cmpRadarKeys.value.length < 3 || !cmpRadarRef.value) return
  if (!cmpRadarChart) cmpRadarChart = echarts.init(cmpRadarRef.value)
  const keys = cmpRadarKeys.value
  cmpRadarChart.setOption(
    {
      legend: { bottom: 0, textStyle: { fontSize: 11, color: '#4b5563' } },
      radar: {
        indicator: keys.map(k => ({ name: JUDGE_METRIC_NAMES[k] || k, max: 1 })),
        radius: '58%',
        axisName: { color: '#6b7280', fontSize: 11 },
        splitArea: { areaStyle: { color: ['#ffffff', '#f7f9fc'] } },
      },
      series: [
        {
          type: 'radar',
          data: rs.map((r, i) => ({
            value: keys.map(k => (r.llmJudge as any)?.[k]?.score ?? 0),
            name: `${String.fromCharCode(65 + i)} · 评估#${compareRecords.value[i]?.id ?? ''}`,
            lineStyle: { color: CMP_RADAR_COLORS[i % 3], width: 2 },
            itemStyle: { color: CMP_RADAR_COLORS[i % 3] },
            areaStyle: { opacity: 0.12, color: CMP_RADAR_COLORS[i % 3] },
          })),
        },
      ],
    },
    { notMerge: true },
  )
}

watch(compareResultVisible, (v) => {
  if (v) nextTick(renderCmpRadar)
})

// ==================== 流式评估（逐指标 SSE 实时出分） ====================
const evalProgress = ref<{ done: number; total: number; current: string } | null>(null)

/** 解析一个 SSE 帧（event: xxx / data: yyy） */
function parseSseFrame(frame: string): { event: string; data: string } | null {
  let event = 'message'
  let data = ''
  for (const line of frame.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) data += line.slice(5).trim()
  }
  return data ? { event, data } : null
}

/** 处理单个评估事件：增量更新 evalResult，实现逐指标出分 */
function handleEvalEvent(event: string, dataStr: string) {
  let data: any
  try {
    data = JSON.parse(dataStr)
  } catch {
    return
  }
  const r = evalResult.value
  if (!r) return
  if (event === 'intrinsic') {
    r.intrinsic = data
  } else if (event === 'metric') {
    r.llmJudge[data.key] = data.data
    if (evalProgress.value) {
      evalProgress.value.done += 1
      evalProgress.value.current = data.label || ''
    }
  } else if (event === 'done') {
    Object.assign(r, data)
  } else if (event === 'saved') {
    r.evaluationId = data.evaluationId
  } else if (event === 'error') {
    ElMessage.error(data.message || '评估失败')
  }
}

async function handleEvaluate() {
  const target = evalTarget.value
  if (!target || (!target.entities?.length && !target.relations?.length)) {
    ElMessage.warning('请选择抽取结果')
    return
  }
  if (!evalTextUsed.value.trim()) {
    ElMessage.warning('缺少评估原文，请选择语料或手动输入原文')
    openCorpusPick()
    return
  }
  if (!selectedMetricKeys.value.length) {
    ElMessage.warning('请至少选择一个评估指标')
    return
  }
  evaluating.value = true
  evalProgress.value = { done: 0, total: selectedMetricKeys.value.length, current: '' }
  // 骨架报告：流式事件逐指标填充，表格/雷达图实时刷新
  evalResult.value = {
    intrinsic: {} as EvalResult['intrinsic'],
    llmJudge: {},
    overall: null,
    sampledRelations: 0,
    sampledEntities: 0,
  }
  try {
    const res = await fetch('/api/extraction/evaluate/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        text: evalTextUsed.value,
        entities: target.entities,
        relations: target.relations,
        sampleSize: evalSampleSize.value,
        llmModelId: evalLlmModelId.value,
        taskId: evalTaskId.value,
        metrics: selectedMetricKeys.value,
      }),
    })
    if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`)
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      let idx: number
      while ((idx = buf.indexOf('\n\n')) >= 0) {
        const frame = buf.slice(0, idx)
        buf = buf.slice(idx + 2)
        const ev = parseSseFrame(frame)
        if (ev) handleEvalEvent(ev.event, ev.data)
      }
    }
    if (evalResult.value?.overall != null) ElMessage.success('评估完成')
  } catch (e) {
    ElMessage.error('评估失败：' + (e as Error).message)
  } finally {
    evaluating.value = false
    evalProgress.value = null
    evalRecordsPage.value = 1
    loadEvalRecords()
  }
}

onMounted(() => {
  loadProjects()
  loadHistory()
  loadExtractLlmModels()
  loadEvalHistory()
  loadEvalRecords()
  loadEvalLlmModels()
})
</script>

<style scoped>
.ext-form :deep(.el-divider--horizontal) {
  margin: 18px 0;
}

.ext-form :deep(.el-divider__text) {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-2);
  background: var(--bg-card);
}

.ext-btn-action {
  width: 100%;
  height: 40px;
  font-size: 15px;
  font-weight: 500;
  transition: transform var(--t-fast), box-shadow var(--t-fast);
}

.ext-btn-action:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 18px rgba(22, 93, 255, 0.22);
}

.ext-btn-action:active {
  transform: translateY(0);
}

.ext-stat-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.ext-result {
  max-height: 560px;
  overflow: auto;
}

.ext-highlight-box {
  margin-bottom: 18px;
}

.ext-section-title {
  font-size: 14px;
  color: var(--text-1);
  margin-bottom: 10px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}

.ext-section-title::before {
  content: '';
  width: 3px;
  height: 14px;
  border-radius: 2px;
  background: linear-gradient(180deg, var(--brand-primary), var(--brand-accent));
}

.ext-highlight-text {
  padding: 16px;
  background: var(--bg-soft);
  border: 1px solid var(--border-2);
  border-radius: var(--r-md);
  line-height: 1.9;
  font-size: 14px;
  color: var(--text-2);
  white-space: pre-wrap;
}

.ext-highlight-text :deep(.hl-entity) {
  border-radius: var(--r-sm);
}

.ext-pagination {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.mb-12 {
  margin-bottom: 12px;
}

.mt-12 {
  margin-top: 12px;
}

/* 语料来源 tab 切换 */
.corpus-source {
  width: 100%;
}

.corpus-tabs {
  display: inline-flex;
  gap: 4px;
  background: var(--border-2);
  padding: 2px;
  border-radius: 6px;
  margin-bottom: 8px;
}

.corpus-tab {
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  color: var(--text-3);
  background: transparent;
  transition: all var(--t-fast);
  user-select: none;
  font-weight: 500;
}

.corpus-tab:hover {
  color: var(--brand-primary);
}

.corpus-tab.active {
  background: #fff;
  color: var(--brand-primary);
  font-weight: 600;
  box-shadow: 0 1px 2px rgba(0, 21, 41, 0.08);
}

.corpus-content {
  width: 100%;
}

/* 实体关系配置 */
.config-tabs :deep(.el-tabs__header) {
  margin-bottom: 18px;
}

.config-tabs :deep(.el-tabs__item) {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-2);
}

.config-tabs :deep(.el-tabs__item.is-active) {
  color: var(--brand-primary);
  font-weight: 600;
}

.config-tabs :deep(.el-tabs__active-bar) {
  background: linear-gradient(90deg, var(--brand-primary), var(--brand-accent));
  height: 3px;
  border-radius: 2px;
}

.ontology-config {
  padding: 4px 0;
}

.ontology-section {
  margin-bottom: 12px;
  padding: 16px;
  background: var(--bg-soft);
  border: 1px solid var(--border-2);
  border-radius: var(--r-md);
}

.ontology-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-1);
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.ontology-title::before {
  content: '';
  width: 3px;
  height: 14px;
  border-radius: 2px;
  background: linear-gradient(180deg, var(--brand-primary), var(--brand-accent));
}

.ontology-sub {
  font-size: 12px;
  color: var(--text-3);
  margin-bottom: 12px;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
  min-height: 36px;
  padding: 10px;
  background: var(--bg-card);
  border-radius: var(--r-md);
  border: 1px dashed var(--border-1);
}

.ontology-tag {
  border-radius: var(--r-sm);
}

.tag-input-row {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-top: 12px;
}

.tag-input-row > :deep(.el-input) {
  flex: 1 1 auto;
}

.tag-input-row > :deep(.el-button) {
  min-width: 88px;
}

.ontology-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 8px;
}

/* ==================== 页面级 Tab ==================== */
.llm-ext-page {
  padding: 20px 24px 28px;
  max-width: 1600px;
  margin: 0 auto;
}

/* ExtractionLayout 自带的页面级 padding/max-width 与外层 .llm-ext-page 重复，
   嵌套后剥离，保证两个 Tab 的面板左边缘/顶部对齐 */
.llm-ext-page :deep(.ext-layout) {
  padding: 0;
  max-width: none;
  margin: 0;
}

/* 页签样式与深度学习抽取页（.dl-tabs）完全统一：card 型 + 渐变顶条 */
.llm-ext-page-tabs > :deep(.el-tabs__header) {
  margin-bottom: 18px;
  border-bottom: 1px solid var(--border-2);
}

.llm-ext-page-tabs > :deep(.el-tabs__header .el-tabs__nav) {
  border: none;
  gap: 8px;
}

.llm-ext-page-tabs > :deep(.el-tabs__header .el-tabs__item) {
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

.llm-ext-page-tabs > :deep(.el-tabs__header .el-tabs__item:hover) {
  color: var(--brand-primary);
  border-color: var(--border-1) !important;
}

.llm-ext-page-tabs > :deep(.el-tabs__header .el-tabs__item.is-active) {
  color: var(--brand-primary);
  background: var(--bg-card);
  border-color: var(--border-2) !important;
  border-bottom: 1px solid var(--bg-card) !important;
  font-weight: 600;
  position: relative;
  top: 1px;
}

.llm-ext-page-tabs > :deep(.el-tabs__header .el-tabs__item.is-active::before) {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, var(--brand-primary), var(--brand-accent));
  border-radius: var(--r-md) var(--r-md) 0 0;
}

/* ==================== 质量评估面板 ==================== */
.eval-layout {
  display: flex;
  flex-direction: column;
  gap: 18px; /* 与知识抽取 Tab 的 .ext-main 间距节奏一致 */
}

.eval-panel {
  background: var(--bg-card, #ffffff);
  border-radius: var(--r-lg, 12px);
  border: 1px solid var(--border-2, #e5e6eb);
  box-shadow: var(--shadow-1, 0 1px 3px rgba(0, 0, 0, 0.04));
  overflow: hidden;
}

.eval-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 20px;
  border-bottom: 1px solid var(--border-2, #e5e6eb);
  background: var(--bg-soft, #f7f8fa);
}

.eval-panel-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-1, #1d2129);
  display: flex;
  align-items: center;
  gap: 10px;
}

.eval-bar {
  width: 3px;
  height: 16px;
  border-radius: 2px;
  background: linear-gradient(180deg, #409eff, var(--brand-accent, #646cff));
}

.eval-panel-body {
  padding: 20px;
}

.eval-header-extra {
  display: flex;
  align-items: center;
  gap: 8px;
}

.eval-sample-text {
  font-size: 12px;
  color: var(--text-3, #86909c);
}

.eval-section-title {
  margin: 16px 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-1, #1f2329);
}

.compare-dialog-tip {
  margin-bottom: 10px;
  font-size: 12px;
  color: var(--text-3, #86909c);
}

/* ===== 对比结果大弹窗（左右两份完整报告） ===== */
.cmp-toolbar {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
}

.cmp-reports {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  align-items: start;
}

.cmp-reports.is-3 {
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
}

.cmp-reports.is-3 .eval-intrinsic-grid {
  grid-template-columns: repeat(2, 1fr);
}

.cmp-reports.is-3 .eval-section-title {
  margin-top: 12px;
}

.cmp-report {
  border: 1px solid var(--el-border-color, #e4e7ed);
  border-radius: 10px;
  background: #fff;
  overflow: hidden;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.cmp-report.is-winner {
  border-color: var(--el-color-success, #67c23a);
  box-shadow: 0 0 0 1px var(--el-color-success, #67c23a) inset;
}

.cmp-report-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: #fafbfc;
  border-bottom: 1px solid var(--el-border-color-light, #ebeef5);
}

.cmp-report-id {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-1, #1f2329);
}

.cmp-report-meta {
  font-size: 12px;
  color: var(--text-3, #86909c);
}

.cmp-report-body {
  padding: 14px;
}

.cmp-report-body .eval-overview {
  flex-direction: column;
  gap: 12px;
}

.cmp-report-body .eval-stat.is-adv {
  border-color: var(--el-color-success, #67c23a);
  background: #f6fcf4;
}

.cmp-report-body .eval-stat.is-adv .eval-stat-value {
  color: var(--el-color-success, #67c23a);
  font-weight: 700;
}

.eval-config {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.eval-task-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.eval-text-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 10px 12px;
  background: var(--bg-soft, #f7f8fa);
  border-radius: var(--r-md, 8px);
}

.eval-corpus-preview {
  margin-top: 10px;
  padding: 10px;
  max-height: 120px;
  overflow: auto;
  background: var(--bg-soft, #f7f8fa);
  border-radius: 6px;
  font-size: 12px;
  color: #6b7280;
  line-height: 1.6;
}

.eval-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.eval-meta-text {
  font-size: 13px;
  color: var(--text-3, #86909c);
  margin-left: 8px;
}

.eval-metrics-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 10px 12px;
  background: var(--bg-soft, #f7f8fa);
  border-radius: var(--r-md, 8px);
}

.eval-metrics-group {
  display: flex;
  align-items: center;
  gap: 4px 16px;
  flex-wrap: wrap;
  flex: 1;
}

.eval-metrics-group :deep(.el-checkbox) {
  margin-right: 0;
  height: auto;
}

.eval-progress-row {
  margin-bottom: 14px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.eval-progress-row :deep(.el-progress) {
  flex: 1;
}

.eval-progress-text {
  font-size: 12px;
  color: #6b7280;
  white-space: nowrap;
}

.eval-radar {
  width: 240px;
  height: 200px;
  flex-shrink: 0;
}

.eval-detail-item.is-clickable {
  cursor: pointer;
  border-radius: 6px;
  padding: 3px 6px;
  margin: 0 -6px;
  transition: background 0.15s;
}

.eval-detail-item.is-clickable:hover {
  background: #f0f4ff;
}

.eval-detail-tip {
  margin-top: 6px;
  font-size: 12px;
  color: #9ca3af;
}

.cmp-radar {
  width: 100%;
  height: 320px;
  margin-bottom: 12px;
}

.drill-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.drill-sample {
  display: flex;
  align-items: center;
  gap: 10px;
}

.drill-sample-text {
  font-size: 14px;
  color: #1f2937;
  font-weight: 500;
}

.drill-reason {
  padding: 8px 12px;
  background: #f7f8fa;
  border-radius: 8px;
  font-size: 13px;
  color: #4b5563;
  line-height: 1.6;
}

.drill-reason-label {
  font-weight: 600;
  color: #1f2937;
}

.drill-text-label {
  font-size: 12px;
  color: #9ca3af;
}

.drill-text {
  max-height: 320px;
  overflow-y: auto;
  padding: 12px 14px;
  background: #f7f9fc;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.9;
  color: #374151;
}

.drill-text :deep(mark) {
  background: #fde68a;
  color: inherit;
  padding: 0 2px;
  border-radius: 3px;
  font-weight: 600;
}

.eval-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.eval-label {
  font-size: 13px;
  color: var(--text-2, #4e5969);
}

.eval-overview {
  display: flex;
  gap: 24px;
  align-items: stretch;
}

.eval-overall-score {
  min-width: 180px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 8px 16px;
  border-right: 1px solid var(--border-2, #e5e6eb);
}

.eval-score-num {
  font-size: 40px;
  font-weight: 700;
  line-height: 1.1;
  color: var(--text-1, #1d2129);
}

.eval-score-num.is-good {
  color: #67c23a;
}

.eval-score-num.is-mid {
  color: #e6a23c;
}

.eval-score-num.is-bad {
  color: #f56c6c;
}

.eval-score-label {
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-3, #86909c);
}

.eval-intrinsic-grid {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.eval-stat {
  background: var(--bg-soft, #f7f8fa);
  border-radius: 8px;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.eval-stat-value {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-1, #1d2129);
}

.eval-stat-label {
  font-size: 12px;
  color: var(--text-3, #86909c);
}

.eval-isolated {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px dashed var(--border-2, #e5e6eb);
}

.eval-isolated-label {
  font-size: 13px;
  color: var(--text-2, #4e5969);
  margin-right: 4px;
}

.eval-isolated-more {
  font-size: 12px;
  color: var(--text-3, #86909c);
}

.eval-detail-list {
  padding: 4px 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.eval-detail-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  flex-wrap: wrap;
}

.eval-detail-item-text {
  font-size: 13px;
  color: var(--text-1, #1d2129);
}

.eval-detail-reason {
  font-size: 12px;
  color: var(--text-3, #86909c);
}

.eval-detail-empty {
  font-size: 13px;
  color: var(--text-3, #86909c);
  padding: 4px 0;
}

.eval-score-none {
  color: var(--text-3, #86909c);
}

.eval-reason-text {
  font-size: 13px;
  color: var(--text-2, #4e5969);
}

/* ==================== 响应式（窄屏评估面板堆叠） ==================== */
@media (max-width: 992px) {
  .eval-overview {
    flex-direction: column;
    gap: 16px;
  }

  .eval-overall-score {
    border-right: none;
    border-bottom: 1px solid var(--border-2, #e5e6eb);
    padding: 0 0 16px;
    min-width: 0;
  }

  .eval-intrinsic-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 600px) {
  .eval-intrinsic-grid {
    grid-template-columns: 1fr;
  }

  .eval-actions {
    flex-wrap: wrap;
  }
}
</style>
