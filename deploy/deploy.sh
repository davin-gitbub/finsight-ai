#!/usr/bin/env bash
# ──── FinSight AI 一键部署脚本 ────
# 用法:
#   ./deploy.sh                     # HTTP 模式部署
#   ./deploy.sh --domain example.com  # 部署 + Let's Encrypt HTTPS
#   ./deploy.sh --skip-ssl            # 跳过 SSL 配置
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DOMAIN=""
SKIP_SSL=false

# --- 解析参数 ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --domain) DOMAIN="$2"; shift 2 ;;
        --skip-ssl) SKIP_SSL=true; shift ;;
        *) echo "未知参数: $1"; echo "用法: ./deploy.sh [--domain example.com] [--skip-ssl]"; exit 1 ;;
    esac
done

echo "╔══════════════════════════════════════╗"
echo "║   FinSight AI  部署脚本              ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "项目目录: $PROJECT_DIR"
echo "域名:     ${DOMAIN:-<未设置，仅 HTTP>}"
echo ""

# ──── 1. 检查前置依赖 ────
echo "[1/6] 检查依赖..."

command -v docker >/dev/null 2>&1 || { echo "❌ 需要安装 Docker: https://docs.docker.com/engine/install/"; exit 1; }
echo "  ✓ Docker"

if ! docker compose version >/dev/null 2>&1; then
    echo "❌ 需要 Docker Compose (已内置在 Docker Desktop 中)"
    exit 1
fi
echo "  ✓ Docker Compose"

command -v node >/dev/null 2>&1 || { echo "❌ 需要安装 Node.js: https://nodejs.org/"; exit 1; }
echo "  ✓ Node.js"

command -v npm >/dev/null 2>&1 || { echo "❌ 需要 npm"; exit 1; }
echo "  ✓ npm"

# ──── 2. 构建前端 Widget ────
echo ""
echo "[2/6] 构建前端 Widget..."

cd "$PROJECT_DIR/widget"
npm ci --silent
npx vite build
WIDGET_SIZE=$(du -sh dist 2>/dev/null | cut -f1)
echo "  ✓ widget/dist 构建完成 (${WIDGET_SIZE})"

# ──── 3. 检查 .env 配置 ────
echo ""
echo "[3/6] 检查环境配置..."

if [ ! -f "$PROJECT_DIR/backend/.env" ]; then
    echo "  ⚠ 未找到 backend/.env"
    if [ -f "$SCRIPT_DIR/.env.example" ]; then
        cp "$SCRIPT_DIR/.env.example" "$PROJECT_DIR/backend/.env"
        echo "  ✓ 已从 deploy/.env.example 创建模板"
        echo ""
        echo "  ┌─────────────────────────────────────────┐"
        echo "  │  请编辑 backend/.env 填入 API Key 后     │"
        echo "  │  重新运行 ./deploy.sh                   │"
        echo "  └─────────────────────────────────────────┘"
        exit 0
    fi
fi
echo "  ✓ backend/.env 存在"

# ──── 4. 构建 Docker 镜像 ────
echo ""
echo "[4/6] 构建 Docker 镜像 (首次构建约 5-10 分钟，含模型下载)..."

cd "$SCRIPT_DIR"
docker compose build backend

echo "  ✓ Docker 镜像构建完成"

# ──── 5. 启动服务 ────
echo ""
echo "[5/6] 启动服务..."

docker compose up -d

# ──── 6. 等待健康检查 ────
echo ""
echo "[6/6] 等待服务就绪..."

for i in $(seq 1 30); do
    if curl -sf http://localhost/health >/dev/null 2>&1; then
        echo "  ✓ 服务健康！"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "  ⚠ 健康检查超时，查看日志: docker compose -f deploy/docker-compose.yml logs"
    fi
    sleep 2
done

# ──── SSL 配置 ────
if [ -n "$DOMAIN" ] && [ "$SKIP_SSL" = false ]; then
    echo ""
    echo "━━━ SSL 配置 ━━━"

    if command -v certbot >/dev/null 2>&1; then
        echo "为 $DOMAIN 申请 Let's Encrypt 证书..."

        # 暂停 nginx，certbot standalone 模式需要 80 端口
        docker compose stop nginx
        sudo certbot certonly --standalone -d "$DOMAIN" --agree-tos --non-interactive --email "admin@${DOMAIN}"

        echo "  ✓ 证书已获取"

        # 启用 HTTPS: 修改 nginx.conf 中的域名
        echo "启用 HTTPS 配置..."
        cd "$SCRIPT_DIR"

        # 取消 HTTP→HTTPS 重定向
        sed -i.bak 's/# return 301 https/return 301 https/' nginx.conf

        # 取消 HTTPS server block 注释
        sed -i.bak 's/# server {/server {/' nginx.conf
        sed -i.bak "s/#     ssl_certificate /    ssl_certificate /" nginx.conf
        sed -i.bak "s/#     ssl_certificate_key/    ssl_certificate_key/" nginx.conf
        sed -i.bak "s/#     ssl_protocols/    ssl_protocols/" nginx.conf
        sed -i.bak "s/#     ssl_ciphers/    ssl_ciphers/" nginx.conf
        sed -i.bak "s/#     gzip/    gzip/" nginx.conf
        sed -i.bak "s/#     gzip_vary/    gzip_vary/" nginx.conf
        sed -i.bak "s/#     gzip_proxied/    gzip_proxied/" nginx.conf
        sed -i.bak "s/#     gzip_comp_level/    gzip_comp_level/" nginx.conf
        sed -i.bak "s/#     gzip_types/    gzip_types/" nginx.conf
        sed -i.bak "s/#     # ---/    # ---/" nginx.conf
        sed -i.bak "s/#     add_header X-Frame/    add_header X-Frame/" nginx.conf
        sed -i.bak "s/#     add_header X-Content/    add_header X-Content/" nginx.conf
        sed -i.bak "s/#     add_header X-XSS/    add_header X-XSS/" nginx.conf
        sed -i.bak "s/#     add_header Referrer/    add_header Referrer/" nginx.conf
        sed -i.bak "s/#     add_header Strict/    add_header Strict/" nginx.conf
        sed -i.bak "s/#     client_max_body_size/    client_max_body_size/" nginx.conf
        sed -i.bak "s/your-domain.com/${DOMAIN}/g" nginx.conf

        # 后续 location blocks 取消注释 (用更简单的方法)
        sed -i.bak "s/#     location /    location /g" nginx.conf
        sed -i.bak "s/#         limit_req/        limit_req/g" nginx.conf
        sed -i.bak "s/#         limit_conn/        limit_conn/g" nginx.conf
        sed -i.bak "s/#         proxy_pass/        proxy_pass/g" nginx.conf
        sed -i.bak "s/#         proxy_http/        proxy_http/g" nginx.conf
        sed -i.bak "s/#         proxy_set_header/        proxy_set_header/g" nginx.conf
        sed -i.bak "s/#         proxy_buffering/        proxy_buffering/g" nginx.conf
        sed -i.bak "s/#         proxy_cache/        proxy_cache/g" nginx.conf
        sed -i.bak "s/#         proxy_read_timeout/        proxy_read_timeout/g" nginx.conf
        sed -i.bak "s/#         proxy_send_timeout/        proxy_send_timeout/g" nginx.conf
        sed -i.bak "s/#         chunked_transfer/        chunked_transfer/g" nginx.conf
        sed -i.bak "s/#         root /        root /g" nginx.conf
        sed -i.bak "s/#         index /        index /g" nginx.conf
        sed -i.bak "s/#         try_files/        try_files/g" nginx.conf
        sed -i.bak "s/#         expires/        expires/g" nginx.conf
        sed -i.bak "s/#         add_header Cache/        add_header Cache/g" nginx.conf
        sed -i.bak "s/#     }/    }/g" nginx.conf

        # 最后一层 } 是 server block 结束
        docker compose start nginx
        docker compose exec nginx nginx -s reload 2>/dev/null || docker compose restart nginx

        # 添加证书自动续期 cron 任务
        (crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet --pre-hook 'cd $SCRIPT_DIR && docker compose stop nginx' --post-hook 'cd $SCRIPT_DIR && docker compose start nginx'") | crontab -

        echo "  ✓ SSL 配置完成"
    else
        echo "  ⚠ certbot 未安装"
        echo "  安装: sudo apt install certbot"
        echo "  然后运行: sudo certbot certonly --standalone -d $DOMAIN"
    fi
fi

# ──── 完成 ────
echo ""
echo "╔══════════════════════════════════════╗"
echo "║   🚀 部署完成！                      ║"
echo "╚══════════════════════════════════════╝"
echo ""
if [ -n "$DOMAIN" ] && [ "$SKIP_SSL" = false ]; then
    echo "  HTTPS: https://${DOMAIN}"
else
    echo "  HTTP:  http://${DOMAIN:-<服务器IP>}"
fi
echo ""
echo "常用命令:"
echo "  查看日志:  docker compose -f deploy/docker-compose.yml logs -f"
echo "  重启后端:  docker compose -f deploy/docker-compose.yml restart backend"
echo "  停止服务:  docker compose -f deploy/docker-compose.yml down"
echo "  数据备份:  docker compose -f deploy/docker-compose.yml exec backend tar czf - /app/chroma_db > chroma_backup.tar.gz"
echo ""
