package com.yuan.seedboot.config;

import com.fasterxml.jackson.databind.module.SimpleModule;
import com.fasterxml.jackson.databind.ser.std.ToStringSerializer;
import org.springframework.boot.autoconfigure.jackson.Jackson2ObjectMapperBuilderCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.TimeZone;

/**
 * Jackson 全局配置
 * 1. 将 Long 类型序列化为 String，防止前端 JavaScript 精度丢失
 * 2. 指定时区为东八区：数据库（CURRENT_TIMESTAMP + serverTimezone=Asia/Shanghai）存的是本地时间，
 *    而 Jackson 默认按 UTC 序列化 Date，会导致前端展示的时间比本地时间早 8 小时
 */
@Configuration
public class JacksonConfig {

    @Bean
    public Jackson2ObjectMapperBuilderCustomizer jackson2ObjectMapperBuilderCustomizer() {
        return builder -> {
            SimpleModule module = new SimpleModule();
            module.addSerializer(Long.class, ToStringSerializer.instance);
            module.addSerializer(Long.TYPE, ToStringSerializer.instance);
            builder.modules(module);
            builder.timeZone(TimeZone.getTimeZone("Asia/Shanghai"));
        };
    }
}
