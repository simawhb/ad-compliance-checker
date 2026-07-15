#!/bin/bash
# 配置 4ma.wang 域名邮箱转发（QQ域名邮箱）
# 用法：bash setup_email_dns.sh

set -e

echo "========================================="
echo "  配置 4ma.wang 域名邮箱 DNS 记录"
echo "  sima@4ma.wang → 14712502@qq.com"
echo "========================================="

# 1. 安装 aliyun CLI
if ! command -v aliyun &>/dev/null; then
    echo "[1/4] 安装 aliyun CLI..."
    cd /tmp
    curl -sSLO https://aliyun-cli.s3.amazonaws.com/aliyun-cli-linux-latest-amd64.tgz
    tar xzf aliyun-cli-linux-latest-amd64.tgz
    chmod +x aliyun
    sudo mv aliyun /usr/local/bin/
    echo "  ✓ aliyun CLI 安装完成"
else
    echo "[1/4] aliyun CLI 已安装"
fi

# 2. 配置 AccessKey
echo "[2/4] 配置 AccessKey..."
aliyun configure set \
    --profile default \
    --access-key-id "YOUR_ALIYUN_ACCESS_KEY_ID" \
    --access-key-secret "YOUR_ALIYUN_ACCESS_KEY_SECRET" \
    --region "cn-hangzhou"

echo "  ✓ AccessKey 配置完成"

# 3. 验证域名归属
echo "[3/4] 验证域名 DNS 状态..."
DOMAIN_INFO=$(aliyun alidns DescribeDomainInfo --DomainName 4ma.wang 2>&1 || true)
if echo "$DOMAIN_INFO" | grep -q "InvalidDomainName\|DomainNotFound"; then
    echo "  ⚠ 域名 4ma.wang 不在当前账号下"
    echo "  （域名可能注册在另一个账号，需要去阿里云 DNS 控制台手动添加记录）"
    echo ""
    echo "  请在浏览器打开以下页面手动配置："
    echo "  https://dns.console.aliyun.com"
    echo ""
    exit 1
fi
echo "  ✓ 域名验证通过"

# 4. 添加 DNS 记录
echo "[4/4] 添加 DNS 记录..."

# 先检查是否已存在相同记录
EXISTING_MX=$(aliyun alidns DescribeDomainRecords --DomainName 4ma.wang --TypeKeyWord MX 2>/dev/null | grep -c "mxdomain.qq.com" || true)
EXISTING_TXT=$(aliyun alidns DescribeDomainRecords --DomainName 4ma.wang --TypeKeyWord TXT 2>/dev/null | grep -c "spf.mail.qq.com" || true)

# 添加 MX 记录（QQ域名邮箱）
if [ "$EXISTING_MX" -eq 0 ]; then
    echo "  - 添加 MX 记录 @ → mxdomain.qq.com (优先级 10)"
    aliyun alidns AddDomainRecord \
        --DomainName 4ma.wang \
        --RR "@" \
        --Type MX \
        --Value "mxdomain.qq.com" \
        --Priority 10
    echo "    ✓ MX 记录已添加"
else
    echo "  - MX 记录已存在，跳过"
fi

# 添加 TXT 记录（SPF 验证）
if [ "$EXISTING_TXT" -eq 0 ]; then
    echo "  - 添加 TXT 记录 @ → v=spf1 include:spf.mail.qq.com ~all"
    aliyun alidns AddDomainRecord \
        --DomainName 4ma.wang \
        --RR "@" \
        --Type TXT \
        --Value "v=spf1 include:spf.mail.qq.com ~all"
    echo "    ✓ TXT 记录已添加"
else
    echo "  - TXT 记录已存在，跳过"
fi

echo ""
echo "========================================="
echo "  DNS 记录配置完成！"
echo ""
echo "  接下来请完成以下步骤："
echo "  1. 访问 https://domain.mail.qq.com 登录 QQ域名邮箱"
echo "  2. 添加域名 4ma.wang（系统会验证 MX 记录）"
echo "  3. 创建邮箱别名 sima，绑定到 14712502@qq.com"
echo "========================================="
