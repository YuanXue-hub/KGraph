# ---------- 构建阶段 ----------
FROM maven:3.9-eclipse-temurin-21 AS builder
WORKDIR /build
# 先拷 pom 预热依赖，利用 Docker 层缓存加速后续构建
COPY pom.xml .
RUN mvn -B -q dependency:go-offline
COPY src ./src
RUN mvn -B -q clean package -DskipTests \
    && mv target/KGraph-0.0.1-SNAPSHOT.jar /build/app.jar

# ---------- 运行阶段 ----------
FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=builder /build/app.jar /app/app.jar
EXPOSE 8888
ENTRYPOINT ["java", "-jar", "/app/app.jar"]

