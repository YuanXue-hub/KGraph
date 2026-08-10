package com.yuan.seedboot.config;

import lombok.extern.slf4j.Slf4j;
import org.neo4j.driver.AuthTokens;
import org.neo4j.driver.Driver;
import org.neo4j.driver.GraphDatabase;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Neo4j 配置类
 * 通过 application.yml 中的 spring.neo4j.* 配置项创建 Driver Bean
 */
@Slf4j
@Configuration
public class Neo4jConfig {

    @Value("${spring.neo4j.uri}")
    private String uri;

    @Value("${spring.neo4j.authentication.username}")
    private String username;

    @Value("${spring.neo4j.authentication.password}")
    private String password;

    @Bean
    public Driver neo4jDriver() {
        log.info("初始化 Neo4j Driver, uri={}, username={}", uri, username);
        return GraphDatabase.driver(uri, AuthTokens.basic(username, password));
    }
}
