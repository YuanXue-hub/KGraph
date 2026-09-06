package com.yuan.seedboot.controller;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.yuan.seedboot.common.BaseResponse;
import com.yuan.seedboot.common.DeleteRequest;
import com.yuan.seedboot.common.ResultUtils;
import com.yuan.seedboot.exception.ErrorCode;
import com.yuan.seedboot.exception.ThrowUtils;
import com.yuan.seedboot.model.entity.Corpus;
import com.yuan.seedboot.model.entity.CorpusChunk;
import com.yuan.seedboot.model.entity.User;
import com.yuan.seedboot.model.request.ChunkCorpusRequest;
import com.yuan.seedboot.model.request.CorpusAddRequest;
import com.yuan.seedboot.model.request.CorpusQueryRequest;
import com.yuan.seedboot.model.request.CorpusUpdateRequest;
import com.yuan.seedboot.model.vo.CorpusChunkStatsVO;
import com.yuan.seedboot.service.CorpusChunkService;
import com.yuan.seedboot.service.CorpusService;
import com.yuan.seedboot.service.UserService;
import io.swagger.v3.oas.annotations.Operation;
import jakarta.annotation.Resource;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

/**
 * 语料 Controller
 */
@RestController
@RequestMapping("/corpus")
public class CorpusController {

    @Resource
    private CorpusService corpusService;

    @Resource
    private CorpusChunkService corpusChunkService;

    @Resource
    private UserService userService;

    @PostMapping("/add")
    @Operation(summary = "新增语料（文本输入）")
    public BaseResponse<Corpus> addCorpus(@RequestBody CorpusAddRequest request, HttpServletRequest httpRequest) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        User loginUser = userService.getLoginUser(httpRequest);
        Corpus corpus = corpusService.addCorpus(request, loginUser);
        return ResultUtils.success(corpus);
    }

    @PostMapping("/upload")
    @Operation(summary = "上传文档创建语料（PDF/Word，异步调用 MinerU 解析）")
    public BaseResponse<Corpus> uploadCorpus(
            @RequestParam("file") MultipartFile file,
            @RequestParam("projectId") Long projectId,
            @RequestParam(value = "title", required = false) String title,
            HttpServletRequest httpRequest) {
        User loginUser = userService.getLoginUser(httpRequest);
        Corpus corpus = corpusService.uploadCorpus(file, projectId, title, loginUser);
        return ResultUtils.success(corpus);
    }

    @PostMapping("/reparse")
    @Operation(summary = "重新解析文档语料")
    public BaseResponse<Boolean> reparseCorpus(@RequestBody DeleteRequest request) {
        ThrowUtils.throwIf(request == null || request.getId() <= 0, ErrorCode.PARAMS_ERROR);
        boolean result = corpusService.reparseCorpus(request.getId());
        return ResultUtils.success(result);
    }

    @PostMapping("/update")
    @Operation(summary = "编辑语料")
    public BaseResponse<Boolean> updateCorpus(@RequestBody CorpusUpdateRequest request) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        boolean result = corpusService.updateCorpus(request);
        return ResultUtils.success(result);
    }

    @PostMapping("/delete")
    @Operation(summary = "删除语料")
    public BaseResponse<Boolean> deleteCorpus(@RequestBody DeleteRequest request) {
        ThrowUtils.throwIf(request == null || request.getId() <= 0, ErrorCode.PARAMS_ERROR);
        boolean result = corpusService.deleteCorpus(request.getId());
        return ResultUtils.success(result);
    }

    @GetMapping("/list")
    @Operation(summary = "语料列表（分页）")
    public BaseResponse<Page<Corpus>> listCorpus(CorpusQueryRequest request) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR);
        Page<Corpus> page = corpusService.listCorpus(request);
        return ResultUtils.success(page);
    }

    @GetMapping("/get")
    @Operation(summary = "语料详情")
    public BaseResponse<Corpus> getCorpus(long id) {
        ThrowUtils.throwIf(id <= 0, ErrorCode.PARAMS_ERROR);
        Corpus corpus = this.corpusService.getById(id);
        ThrowUtils.throwIf(corpus == null, ErrorCode.NOT_FOUND_ERROR);
        return ResultUtils.success(corpus);
    }

    // ==================== 语料分块 ====================

    @PostMapping("/{id}/chunks/preview")
    @Operation(summary = "分块预览（dry-run 不落库，返回统计 + 前 10 块）")
    public BaseResponse<CorpusChunkStatsVO> previewChunks(@PathVariable("id") long id,
                                                          @RequestBody ChunkCorpusRequest request) {
        ThrowUtils.throwIf(id <= 0, ErrorCode.PARAMS_ERROR);
        return ResultUtils.success(this.corpusChunkService.previewChunks(id, request));
    }

    @PostMapping("/{id}/chunks")
    @Operation(summary = "执行分块（覆盖式重建落库）")
    public BaseResponse<CorpusChunkStatsVO> chunkCorpus(@PathVariable("id") long id,
                                                        @RequestBody ChunkCorpusRequest request,
                                                        HttpServletRequest httpRequest) {
        ThrowUtils.throwIf(id <= 0, ErrorCode.PARAMS_ERROR);
        User loginUser = this.userService.getLoginUser(httpRequest);
        return ResultUtils.success(this.corpusChunkService.chunkCorpus(id, request, loginUser.getId()));
    }

    @GetMapping("/{id}/chunks")
    @Operation(summary = "分页查看分块结果")
    public BaseResponse<Page<CorpusChunk>> listChunks(@PathVariable("id") long id,
                                                      @RequestParam(defaultValue = "1") long pageNum,
                                                      @RequestParam(defaultValue = "20") long pageSize) {
        ThrowUtils.throwIf(id <= 0, ErrorCode.PARAMS_ERROR);
        return ResultUtils.success(this.corpusChunkService.pageChunks(id, pageNum, pageSize));
    }

    @DeleteMapping("/{id}/chunks")
    @Operation(summary = "清空语料分块")
    public BaseResponse<Boolean> clearChunks(@PathVariable("id") long id) {
        ThrowUtils.throwIf(id <= 0, ErrorCode.PARAMS_ERROR);
        return ResultUtils.success(this.corpusChunkService.clearChunks(id));
    }
}
