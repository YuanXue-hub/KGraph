package com.yuan.seedboot.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.yuan.seedboot.model.entity.CorpusChunk;
import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.List;
import java.util.Map;

/**
 * 语料分块数据库操作
 */
public interface CorpusChunkMapper extends BaseMapper<CorpusChunk> {

    /**
     * 物理删除某语料全部分块（覆盖式重建/失效清理用，不走逻辑删除）
     */
    @Delete("DELETE FROM corpus_chunk WHERE corpusId = #{corpusId}")
    int deleteByCorpusId(@Param("corpusId") Long corpusId);

    /**
     * 按语料 ID 集合统计分块数（列表页 chunkCount 填充）
     */
    @Select("<script>SELECT corpusId, COUNT(*) AS cnt FROM corpus_chunk " +
            "WHERE isDeleted = 0 AND corpusId IN " +
            "<foreach collection='corpusIds' item='id' open='(' separator=',' close=')'>#{id}</foreach> " +
            "GROUP BY corpusId</script>")
    List<Map<String, Object>> countByCorpusIds(@Param("corpusIds") List<Long> corpusIds);
}
