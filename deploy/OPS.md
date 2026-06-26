# FinSight AI — 运维手册

## 服务器信息

| 项目           | 值                                                   |
| -------------- | ---------------------------------------------------- |
| 域名           | `https://finsight.hkharbor.com`                      |
| 部署路径       | `/home/deploy/finsight-ai`                           |
| Docker Compose | `/home/deploy/finsight-ai/deploy/docker-compose.yml` |
| Nginx 配置     | `/home/deploy/finsight-ai/deploy/nginx.conf`         |

---

## 服务管理

全部在 `~/finsight-ai/deploy/` 目录下执行。

### 启动

```bash
cd ~/finsight-ai/deploy
docker compose up -d
```

### 停止

```bash
cd ~/finsight-ai/deploy
docker compose down
```

### 重启

```bash
# 重启后端（更新代码后）
docker compose restart backend

# 重启 Nginx（修改 nginx.conf 后）
docker restart finsight-nginx

# 全部重启
docker compose restart
```

### 查看状态

```bash
docker compose ps
```

### 查看日志

```bash
# 实时日志（后端）
docker compose logs -f backend

# 实时日志（Nginx 访问日志）
docker logs -f finsight-nginx

# 最近 50 行
docker compose logs --tail 50 backend
```

---

## SSL 证书

### 查看到期时间

```bash
sudo openssl x509 -in /etc/letsencrypt/live/finsight.hkharbor.com/cert.pem -noout -enddate
```

### 模拟续期测试

```bash
sudo certbot renew --dry-run
```

### 手动续期

```bash
sudo certbot renew
```

### 自动续期机制

- certbot 自带定时任务，每天检查 2 次
- 到期前 30 天自动续期
- 续期时自动执行：停止 Nginx → 续期 → 启动 Nginx（约 3 秒）
- 查看定时任务：`sudo systemctl list-timers | grep certbot`

---

## 更新代码

```bash
cd ~/finsight-ai
git pull origin main
cd deploy

# 重新构建前端（如果 widget 有改动）
cd ../widget && npm ci && npx vite build && cd ../deploy

# 重启服务
docker compose restart backend
docker restart finsight-nginx
```

---

## 数据备份

```bash
# ChromaDB 向量数据
docker exec finsight-backend tar czf - /app/chroma_db > chroma_backup_$(date +%Y%m%d).tar.gz

# 用户反馈数据
docker cp finsight-backend:/app/feedback/feedback.jsonl feedback_backup_$(date +%Y%m%d).jsonl
```

---

## 故障排查

```bash
# 服务不健康
docker compose ps

# 查看后端错误
docker logs finsight-backend --tail 100

# 查看 Nginx 错误
docker logs finsight-nginx 2>&1 | grep -i error | tail -20

# 本地测试 API
curl http://localhost/health
curl -k https://localhost/health

# 测试聊天接口
curl -X POST http://localhost/api/chat \
  -H "Content-Type: application/json" \
  -H "User-Agent: Mozilla/5.0" \
  -d '{"content":"你好","tenant":"finsight"}'
```

---

## 端口说明

| 端口 | 用途                   | 对外   |
| ---- | ---------------------- | ------ |
| 80   | HTTP（重定向到 HTTPS） | 开放   |
| 443  | HTTPS                  | 开放   |
| 8000 | 后端（仅容器内部）     | 不暴露 |
