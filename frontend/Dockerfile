# ---------- 构建阶段 ----------
FROM node:18-alpine AS builder
WORKDIR /build
COPY package*.json ./
RUN npm ci
COPY . .
# npm run build = vue-tsc --noEmit && vite build
RUN npm run build

# ---------- 运行阶段 ----------
FROM nginx:1.27-alpine
COPY --from=builder /build/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

