# 构建阶段
FROM node:20-alpine AS builder

WORKDIR /app

# 复制依赖文件
COPY package.json ./
RUN npm install

# 创建空的 postcss 配置文件，防止 vite 搜索时误解析 package.json
RUN echo 'module.exports = {}' > postcss.config.js

# 复制源码并构建（精确复制必要的文件，排除 package.json 的重复复制）
COPY index.html ./
COPY vite.config.js ./
COPY nginx.conf ./
COPY src ./src
RUN if [ -d public ] && [ -n "$(ls -A public 2>/dev/null)" ]; then cp -r public/* ./public/ 2>/dev/null || mkdir -p ./public; else mkdir -p ./public; fi

RUN npm run build

# 生产阶段 - 使用Nginx
FROM nginx:alpine

# 复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制nginx配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 暴露端口
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
