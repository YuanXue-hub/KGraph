package com.yuan.seedboot;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableAsync;

@SpringBootApplication
@MapperScan("com.yuan.seedboot.mapper")
@EnableAsync
public class SeedBootApplication {

    public static void main(String[] args) {
        SpringApplication.run(SeedBootApplication.class, args);
    }

}
