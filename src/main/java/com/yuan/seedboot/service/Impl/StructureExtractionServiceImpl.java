package com.yuan.seedboot.service.Impl;

import cn.hutool.core.util.StrUtil;
import cn.hutool.json.JSONUtil;
import com.yuan.seedboot.exception.BusinessException;
import com.yuan.seedboot.exception.ErrorCode;
import com.yuan.seedboot.exception.ThrowUtils;
import com.yuan.seedboot.model.entity.ExtractionTask;
import com.yuan.seedboot.model.entity.User;
import com.yuan.seedboot.model.request.StructureExtractionRequest;
import com.yuan.seedboot.service.ExtractionTaskService;
import com.yuan.seedboot.service.StructureExtractionService;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.apache.poi.ss.usermodel.*;
import org.neo4j.driver.Driver;
import org.neo4j.driver.Session;
import org.springframework.stereotype.Service;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

/**
 * （半）结构化数据抽取服务实现
 * 支持 CSV / Excel(xlsx) 文件解析，按字段映射写入 Neo4j
 */
@Slf4j
@Service
public class StructureExtractionServiceImpl implements StructureExtractionService {

    private static final String TEMP_DIR = System.getProperty("java.io.tmpdir") + "/kgraph_structure/";
    private static final int PREVIEW_ROW_COUNT = 10;

    @Resource
    private Driver neo4jDriver;

    @Resource
    private ExtractionTaskService extractionTaskService;

    static {
        try {
            Files.createDirectories(Path.of(TEMP_DIR));
        } catch (IOException e) {
            // 忽略目录创建失败
        }
    }

    // ============================================================
    // 文件解析
    // ============================================================

    @Override
    public Map<String, Object> parseFile(byte[] fileBytes, String fileName) {
        ThrowUtils.throwIf(fileBytes == null || fileBytes.length == 0, ErrorCode.PARAMS_ERROR, "文件内容为空");
        ThrowUtils.throwIf(StrUtil.isBlank(fileName), ErrorCode.PARAMS_ERROR, "文件名为空");

        String lowerName = fileName.toLowerCase();
        List<String> columns;
        List<Map<String, String>> allRows;

        if (lowerName.endsWith(".csv")) {
            String content = new String(fileBytes, StandardCharsets.UTF_8);
            allRows = parseCsv(content);
        } else if (lowerName.endsWith(".xlsx") || lowerName.endsWith(".xls")) {
            try (Workbook workbook = WorkbookFactory.create(new ByteArrayInputStream(fileBytes))) {
                allRows = parseExcel(workbook);
            } catch (IOException e) {
                throw new BusinessException(ErrorCode.OPERATION_ERROR, "Excel 文件解析失败: " + e.getMessage());
            }
        } else {
            throw new BusinessException(ErrorCode.PARAMS_ERROR, "不支持的文件格式，仅支持 CSV / Excel(xlsx)");
        }

        ThrowUtils.throwIf(allRows.isEmpty(), ErrorCode.PARAMS_ERROR, "文件无有效数据行");

        // 提取列名（取第一行所有 key）
        columns = new ArrayList<>(allRows.get(0).keySet());

        // 预览前 N 行
        List<Map<String, String>> previewRows = allRows.subList(0, Math.min(PREVIEW_ROW_COUNT, allRows.size()));

        // 保存临时文件，返回 fileKey
        String fileKey = UUID.randomUUID().toString().replace("-", "");
        try {
            Path filePath = Path.of(TEMP_DIR, fileKey + ".dat");
            Files.write(filePath, fileBytes);
            // 同时保存文件名，用于后续解析格式
            Files.writeString(Path.of(TEMP_DIR, fileKey + ".name"), fileName);
        } catch (IOException e) {
            throw new BusinessException(ErrorCode.OPERATION_ERROR, "临时文件保存失败: " + e.getMessage());
        }

        Map<String, Object> result = new HashMap<>();
        result.put("fileKey", fileKey);
        result.put("fileName", fileName);
        result.put("columns", columns);
        result.put("previewRows", previewRows);
        result.put("totalRows", allRows.size());
        return result;
    }

    /**
     * 解析 CSV 文件（支持逗号分隔，首行为表头）
     */
    private List<Map<String, String>> parseCsv(String content) {
        List<Map<String, String>> rows = new ArrayList<>();
        String[] lines = content.split("\n");
        if (lines.length == 0) return rows;

        // 解析表头
        String[] headers = parseCsvLine(lines[0]);
        for (int i = 1; i < lines.length; i++) {
            String line = lines[i].trim();
            if (line.isEmpty()) continue;
            String[] values = parseCsvLine(line);
            Map<String, String> row = new LinkedHashMap<>();
            for (int j = 0; j < headers.length; j++) {
                String val = j < values.length ? values[j].trim() : "";
                row.put(headers[j].trim(), val);
            }
            rows.add(row);
        }
        return rows;
    }

    /**
     * 解析单行 CSV（支持双引号包裹）
     */
    private String[] parseCsvLine(String line) {
        List<String> result = new ArrayList<>();
        StringBuilder sb = new StringBuilder();
        boolean inQuotes = false;
        for (int i = 0; i < line.length(); i++) {
            char c = line.charAt(i);
            if (c == '"') {
                inQuotes = !inQuotes;
            } else if (c == ',' && !inQuotes) {
                result.add(sb.toString());
                sb.setLength(0);
            } else {
                sb.append(c);
            }
        }
        result.add(sb.toString());
        return result.toArray(new String[0]);
    }

    /**
     * 解析 Excel 文件（首行为表头）
     */
    private List<Map<String, String>> parseExcel(Workbook workbook) {
        List<Map<String, String>> rows = new ArrayList<>();
        Sheet sheet = workbook.getSheetAt(0);
        if (sheet.getPhysicalNumberOfRows() == 0) return rows;

        // 解析表头
        Row headerRow = sheet.getRow(0);
        if (headerRow == null) return rows;
        List<String> headers = new ArrayList<>();
        for (int i = 0; i < headerRow.getLastCellNum(); i++) {
            Cell cell = headerRow.getCell(i);
            headers.add(cell == null ? "column_" + i : getCellValueAsString(cell));
        }

        // 解析数据行
        for (int r = 1; r <= sheet.getLastRowNum(); r++) {
            Row row = sheet.getRow(r);
            if (row == null) continue;
            Map<String, String> rowData = new LinkedHashMap<>();
            boolean hasData = false;
            for (int c = 0; c < headers.size(); c++) {
                Cell cell = row.getCell(c);
                String val = cell == null ? "" : getCellValueAsString(cell);
                if (!val.isEmpty()) hasData = true;
                rowData.put(headers.get(c), val);
            }
            if (hasData) rows.add(rowData);
        }
        return rows;
    }

    /**
     * Excel 单元格值转字符串
     */
    private String getCellValueAsString(Cell cell) {
        if (cell == null) return "";
        return switch (cell.getCellType()) {
            case STRING -> cell.getStringCellValue().trim();
            case NUMERIC -> {
                double d = cell.getNumericCellValue();
                if (d == Math.floor(d)) yield String.valueOf((long) d);
                else yield String.valueOf(d);
            }
            case BOOLEAN -> String.valueOf(cell.getBooleanCellValue());
            case FORMULA -> {
                try {
                    yield cell.getStringCellValue().trim();
                } catch (Exception e) {
                    yield String.valueOf(cell.getNumericCellValue());
                }
            }
            default -> "";
        };
    }

    /**
     * 从临时文件重新加载数据行
     */
    private List<Map<String, String>> loadRowsFromFile(String fileKey) {
        try {
            Path filePath = Path.of(TEMP_DIR, fileKey + ".dat");
            Path namePath = Path.of(TEMP_DIR, fileKey + ".name");
            ThrowUtils.throwIf(!Files.exists(filePath), ErrorCode.PARAMS_ERROR, "文件已过期，请重新上传");
            byte[] bytes = Files.readAllBytes(filePath);
            String fileName = Files.exists(namePath) ? Files.readString(namePath) : "";
            String lowerName = fileName.toLowerCase();

            if (lowerName.endsWith(".csv")) {
                return parseCsv(new String(bytes, StandardCharsets.UTF_8));
            } else if (lowerName.endsWith(".xlsx") || lowerName.endsWith(".xls")) {
                try (Workbook workbook = WorkbookFactory.create(new ByteArrayInputStream(bytes))) {
                    return parseExcel(workbook);
                }
            }
            throw new BusinessException(ErrorCode.PARAMS_ERROR, "不支持的文件格式");
        } catch (IOException e) {
            throw new BusinessException(ErrorCode.OPERATION_ERROR, "文件读取失败: " + e.getMessage());
        }
    }

    // ============================================================
    // 执行抽取
    // ============================================================

    @Override
    public ExtractionTask executeExtraction(StructureExtractionRequest request, User loginUser) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        ThrowUtils.throwIf(request.getProjectId() == null, ErrorCode.PARAMS_ERROR, "项目 id 为空");
        ThrowUtils.throwIf(request.getModelId() == null, ErrorCode.PARAMS_ERROR, "模型 id 为空");
        ThrowUtils.throwIf(StrUtil.isBlank(request.getFileKey()), ErrorCode.PARAMS_ERROR, "文件 key 为空");

        // 1. 加载数据行
        List<Map<String, String>> rows = loadRowsFromFile(request.getFileKey());
        ThrowUtils.throwIf(rows.isEmpty(), ErrorCode.PARAMS_ERROR, "文件无有效数据行");

        // 2. 创建任务记录
        ExtractionTask task = new ExtractionTask();
        task.setProjectId(request.getProjectId());
        task.setModelId(request.getModelId());
        task.setExtractionType("STRUCTURE");
        task.setInputConfig(JSONUtil.toJsonStr(request));
        task.setInputText("结构化文件抽取，共 " + rows.size() + " 行");
        task.setStatus(1);
        task.setTokenConsumed(0);
        task.setDuration(0L);
        task.setCreateBy(loginUser.getId());
        boolean saved = extractionTaskService.save(task);
        ThrowUtils.throwIf(!saved, ErrorCode.OPERATION_ERROR, "创建抽取任务失败");

        // 3. 执行写入
        long startTs = System.currentTimeMillis();
        try {
            Map<String, Object> writeResult = writeToNeo4j(request, rows);
            // 4. 填充结果
            Map<String, Object> resultData = new HashMap<>();
            resultData.put("writeCount", writeResult);
            resultData.put("totalRows", rows.size());
            resultData.put("entities", writeResult.get("entities"));
            resultData.put("relations", writeResult.get("relations"));

            task.setResult(JSONUtil.toJsonStr(resultData));
            task.setStatus(2);
            task.setDuration(System.currentTimeMillis() - startTs);
        } catch (Exception e) {
            log.error("结构化抽取执行失败, taskId={}", task.getId(), e);
            task.setStatus(3);
            task.setDuration(System.currentTimeMillis() - startTs);
            extractionTaskService.updateById(task);
            throw e instanceof BusinessException ? (BusinessException) e
                    : new BusinessException(ErrorCode.OPERATION_ERROR, "结构化抽取执行失败: " + e.getMessage());
        }
        extractionTaskService.updateById(task);

        // 5. 清理临时文件
        cleanupTempFile(request.getFileKey());

        return task;
    }

    /**
     * 按映射配置将数据批量写入 Neo4j
     */
    private Map<String, Object> writeToNeo4j(StructureExtractionRequest request, List<Map<String, String>> rows) {
        Long modelId = request.getModelId();
        int entityCount = 0;
        int relationCount = 0;
        int failCount = 0;

        try (Session session = neo4jDriver.session()) {
            // 写入实体
            if (request.getEntityMappings() != null) {
                for (StructureExtractionRequest.EntityMapping em : request.getEntityMappings()) {
                    if (StrUtil.isBlank(em.getEntityTypeName()) || StrUtil.isBlank(em.getNameColumn())) {
                        continue;
                    }
                    for (Map<String, String> row : rows) {
                        try {
                            String name = row.get(em.getNameColumn());
                            if (StrUtil.isBlank(name)) {
                                failCount++;
                                continue;
                            }
                            Map<String, Object> props = new HashMap<>();
                            if (em.getPropertyMappings() != null) {
                                for (StructureExtractionRequest.PropertyMapping pm : em.getPropertyMappings()) {
                                    if (StrUtil.isNotBlank(pm.getSourceColumn()) && StrUtil.isNotBlank(pm.getTargetProperty())) {
                                        String val = row.get(pm.getSourceColumn());
                                        if (StrUtil.isNotBlank(val)) {
                                            props.put(pm.getTargetProperty(), convertValue(val));
                                        }
                                    }
                                }
                            }
                            session.run(
                                    "MERGE (n:Entity {name: $name, type: $type, modelId: $modelId}) " +
                                            "SET n += $properties, n.createTime = timestamp()",
                                    Map.of(
                                            "name", name,
                                            "type", em.getEntityTypeName(),
                                            "modelId", modelId,
                                            "properties", props
                                    )
                            );
                            entityCount++;
                        } catch (Exception e) {
                            log.warn("实体写入失败: row={}, error={}", row, e.getMessage());
                            failCount++;
                        }
                    }
                }
            }

            // 写入关系
            if (request.getRelationMappings() != null) {
                for (StructureExtractionRequest.RelationMapping rm : request.getRelationMappings()) {
                    if (StrUtil.isBlank(rm.getRelationTypeName())
                            || StrUtil.isBlank(rm.getHeadNameColumn())
                            || StrUtil.isBlank(rm.getTailNameColumn())) {
                        continue;
                    }
                    for (Map<String, String> row : rows) {
                        try {
                            String headName = row.get(rm.getHeadNameColumn());
                            String tailName = row.get(rm.getTailNameColumn());
                            if (StrUtil.isBlank(headName) || StrUtil.isBlank(tailName)) {
                                failCount++;
                                continue;
                            }
                            Map<String, Object> props = new HashMap<>();
                            if (rm.getPropertyMappings() != null) {
                                for (StructureExtractionRequest.PropertyMapping pm : rm.getPropertyMappings()) {
                                    if (StrUtil.isNotBlank(pm.getSourceColumn()) && StrUtil.isNotBlank(pm.getTargetProperty())) {
                                        String val = row.get(pm.getSourceColumn());
                                        if (StrUtil.isNotBlank(val)) {
                                            props.put(pm.getTargetProperty(), convertValue(val));
                                        }
                                    }
                                }
                            }
                            session.run(
                                    "MATCH (a:Entity {name: $head, modelId: $modelId}), " +
                                            "(b:Entity {name: $tail, modelId: $modelId}) " +
                                            "MERGE (a)-[rel:RELATION {relationType: $relationType, modelId: $modelId}]->(b) " +
                                            "SET rel += $properties, rel.createTime = timestamp(), rel.type = $relationType",
                                    Map.of(
                                            "head", headName,
                                            "tail", tailName,
                                            "relationType", rm.getRelationTypeName(),
                                            "modelId", modelId,
                                            "properties", props
                                    )
                            );
                            relationCount++;
                        } catch (Exception e) {
                            log.warn("关系写入失败: row={}, error={}", row, e.getMessage());
                            failCount++;
                        }
                    }
                }
            }
        }

        Map<String, Object> result = new HashMap<>();
        result.put("entities", entityCount);
        result.put("relations", relationCount);
        result.put("failed", failCount);
        return result;
    }

    /**
     * 值类型转换：尝试将字符串转为数值，否则保留字符串
     */
    private Object convertValue(String val) {
        if (val == null) return "";
        val = val.trim();
        try {
            double d = Double.parseDouble(val);
            if (d == Math.floor(d) && !val.contains(".")) {
                return (long) d;
            }
            return d;
        } catch (NumberFormatException e) {
            // 尝试布尔值
            if ("true".equalsIgnoreCase(val)) return true;
            if ("false".equalsIgnoreCase(val)) return false;
            return val;
        }
    }

    /**
     * 清理临时文件
     */
    private void cleanupTempFile(String fileKey) {
        try {
            Files.deleteIfExists(Path.of(TEMP_DIR, fileKey + ".dat"));
            Files.deleteIfExists(Path.of(TEMP_DIR, fileKey + ".name"));
        } catch (IOException e) {
            // 忽略
        }
    }
}
