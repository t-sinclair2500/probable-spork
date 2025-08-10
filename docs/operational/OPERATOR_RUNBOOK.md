# Operator Runbook — One-Pi Shared Pipeline

## First-time bootstrap

### Core Pipeline Setup
```bash
make install
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable --now ollama
cp conf/global.example.yaml conf/global.yaml
cp .env.example .env  # Comprehensive environment variables template
# Edit .env with your actual API keys and credentials
make check
```

### WordPress Setup (Required for Blog Pipeline)

**You need WordPress running before using the blog pipeline.** Choose one option:

#### Option 1: Cloud WordPress (Easiest)
1. Sign up with managed WordPress hosting (Bluehost, SiteGround, etc.)
2. Get your WordPress URL: `https://yoursite.com`
3. Create a non-admin user for posting (e.g., "content_poster")
4. Generate Application Password: WP Admin > Users > Application Passwords

#### Option 2: WordPress on Pi (Local)
```bash
# Install LAMP stack
sudo apt update
sudo apt install apache2 mysql-server php php-mysql php-curl php-gd php-mbstring php-xml

# Download WordPress
cd /var/www/html
sudo wget https://wordpress.org/latest.tar.gz
sudo tar -xzf latest.tar.gz
sudo mv wordpress/* .
sudo chown -R www-data:www-data /var/www/html

# Setup MySQL database
sudo mysql_secure_installation
sudo mysql -u root -p
CREATE DATABASE wordpress;
CREATE USER 'wp_user'@'localhost' IDENTIFIED BY 'secure_password';
GRANT ALL PRIVILEGES ON wordpress.* TO 'wp_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;

# Complete setup: http://your-pi-ip/wp-admin/install.php
# Your Pi's IP will be something like: http://192.168.1.100

# Find your Pi's IP address:
hostname -I | awk '{print $1}'
```

#### Option 3: WordPress via Docker
```bash
mkdir ~/wordpress && cd ~/wordpress
cat > docker-compose.yml << 'EOF'
version: '3.8'
services:
  wordpress:
    image: wordpress:latest
    ports:
      - "8080:80"
    environment:
      WORDPRESS_DB_HOST: db
      WORDPRESS_DB_USER: wordpress
      WORDPRESS_DB_PASSWORD: wordpress
      WORDPRESS_DB_NAME: wordpress
    volumes:
      - wordpress:/var/www/html
  db:
    image: mysql:5.7
    environment:
      MYSQL_DATABASE: wordpress
      MYSQL_USER: wordpress
      MYSQL_PASSWORD: wordpress
      MYSQL_ROOT_PASSWORD: rootpassword
    volumes:
      - db:/var/lib/mysql
volumes:
  wordpress:
  db:
EOF

docker-compose up -d
# Access at http://localhost:8080 (from Pi) or http://your-pi-ip:8080 (from other devices)
```

### Blog Pipeline Configuration
```bash
cp conf/blog.example.yaml conf/blog.yaml
# Edit conf/blog.yaml with your WordPress URL and credentials
```

## Manual one-shot
```bash
source .venv/bin/activate
make run-once
make blog-once
```

## Cron install
```bash
crontab ops/crontab.seed.txt
```

## Health server & systemd
```bash
sudo bash scripts/install_systemd_and_logrotate.sh
# Health at http://PI:8088/health
```

## Backups
```bash
make backup
```

## Restore (outline)
1) Reinstall packages & clone repo.
2) Restore WP DB + wp-content from backups.
3) Restore repo backups to `data/` and media dirs.
4) Recreate application passwords for WordPress poster.

## Publishing Control & Toggles

**Centralized Flag Governance** - all publishing uses the same precedence hierarchy:
1. **CLI flags** (highest): `--dry-run` forces dry-run mode
2. **Environment variables**: `BLOG_DRY_RUN`, `YOUTUBE_UPLOAD_DRY_RUN`
3. **Config files**: `wordpress.publish_enabled` in `conf/blog.yaml`
4. **Safe defaults** (lowest): dry-run enabled, publishing disabled

**Enable Live Publishing:**
```bash
# Blog publishing (both required):
echo "  publish_enabled: true" >> conf/blog.yaml
echo "BLOG_DRY_RUN=false" >> .env

# YouTube uploads:
echo "YOUTUBE_UPLOAD_DRY_RUN=false" >> .env

# Check current status:
python -c "from bin.core import get_publish_summary; print(get_publish_summary())"
```

**Emergency Dry-Run Override:**
```bash
# Force all publishing to dry-run regardless of config:
python bin/run_pipeline.py --dry-run
```

## Troubleshooting
- Check `logs/pipeline.log` and `jobs/state.jsonl`.
- Ensure GPU split low and swap on SSD.
- If CPU temp > 75°C, pipeline defers heavy steps.
- **Publishing Issues**: Use `get_publish_summary()` to check flag hierarchy and current settings.
- **Missing API keys**: The comprehensive `.env.example` file documents all available environment variables. Copy to `.env` and configure your actual API keys. `make check` reports missing keys and suggests which features will be skipped.
  - Asset providers: `PIXABAY_API_KEY`, `PEXELS_API_KEY`, `UNSPLASH_ACCESS_KEY` (optional)
  - Data ingestion: `YOUTUBE_API_KEY`, Reddit API credentials
  - Optional services: OpenAI API key for TTS/ASR fallbacks
- **Note**: `.env` files are excluded from version control for security. Always use `.env.example` as your template.
