# 🚀 Deployment Guide

## Production Deployment Checklist

### 1. Environment Configuration

Create a production `.env` file:

```bash
DEBUG=False
SECRET_KEY=your-super-secret-production-key-here
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database (PostgreSQL recommended)
DATABASE_URL=postgres://user:password@host:port/database

# Redis
REDIS_URL=redis://your-redis-host:6379

# Email
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-specific-password
DEFAULT_FROM_EMAIL=noreply@yourdomain.com
```

### 2. Database Setup

**PostgreSQL (Recommended)**

```bash
# Install psycopg2
pip install psycopg2-binary

# Update settings.py to use DATABASE_URL
# Already configured with django-environ
```

**Run Migrations**
```bash
python manage.py migrate
python manage.py createsuperuser
```

### 3. Static Files

```bash
# Collect static files
python manage.py collectstatic --noinput
```

### 4. ASGI Server Setup

**Using Daphne (Recommended for WebSocket support)**

```bash
# Install daphne
pip install daphne

# Run with:
daphne -b 0.0.0.0 -p 8000 attendance_system.asgi:application
```

**Using Gunicorn + Daphne**

```bash
# For HTTP requests
gunicorn attendance_system.wsgi:application

# For WebSocket (separate process)
daphne attendance_system.asgi:application
```

### 5. Redis Setup

**Docker**
```bash
docker run -d -p 6379:6379 redis:alpine
```

**System Service**
```bash
sudo apt-get install redis-server
sudo systemctl start redis
sudo systemctl enable redis
```

### 6. Nginx Configuration

```nginx
upstream django {
    server 127.0.0.1:8000;
}

upstream daphne {
    server 127.0.0.1:8001;
}

server {
    listen 80;
    server_name yourdomain.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # Static files
    location /static/ {
        alias /path/to/project/staticfiles/;
    }

    location /media/ {
        alias /path/to/project/media/;
    }

    # WebSocket
    location /ws/ {
        proxy_pass http://daphne;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Django
    location / {
        proxy_pass http://django;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 7. Systemd Services

**Django Service** (`/etc/systemd/system/attendance-django.service`)
```ini
[Unit]
Description=Attendance System Django
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/project
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/daphne -b 127.0.0.1 -p 8000 attendance_system.asgi:application
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

**Enable and Start**
```bash
sudo systemctl daemon-reload
sudo systemctl start attendance-django
sudo systemctl enable attendance-django
```

### 8. Security Checklist

- [ ] Set `DEBUG=False`
- [ ] Use strong `SECRET_KEY`
- [ ] Configure `ALLOWED_HOSTS`
- [ ] Enable HTTPS/SSL
- [ ] Set up firewall (ufw/iptables)
- [ ] Configure CSRF settings
- [ ] Set up database backups
- [ ] Enable Redis password protection
- [ ] Configure email securely
- [ ] Set up monitoring/logging

### 9. Performance Optimization

**Database Indexes**
```bash
python manage.py migrate
```

**Redis Configuration**
```bash
# In redis.conf
maxmemory 256mb
maxmemory-policy allkeys-lru
```

**Static Files CDN**
```python
# Use WhiteNoise or CDN for static files
pip install whitenoise
```

### 10. Monitoring

**Logging**
```python
# Add to settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': '/path/to/logs/django.log',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'ERROR',
            'propagate': True,
        },
    },
}
```

## Cloud Deployment Options

### Heroku

```bash
# Install Heroku CLI
heroku login
heroku create your-app-name

# Add Redis
heroku addons:create heroku-redis:hobby-dev

# Add PostgreSQL
heroku addons:create heroku-postgresql:hobby-dev

# Deploy
git push heroku main
heroku run python manage.py migrate
```

### DigitalOcean App Platform

1. Connect GitHub repository
2. Set environment variables
3. Add Redis managed database
4. Add PostgreSQL managed database
5. Deploy

### AWS Elastic Beanstalk

```bash
eb init
eb create production
eb deploy
```

### Docker Deployment

**Dockerfile**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "attendance_system.asgi:application"]
```

**docker-compose.yml**
```yaml
version: '3.8'

services:
  redis:
    image: redis:alpine
    ports:
      - "6379:6379"

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: attendance
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  web:
    build: .
    command: daphne -b 0.0.0.0 -p 8000 attendance_system.asgi:application
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    depends_on:
      - redis
      - postgres
    environment:
      - DATABASE_URL=postgres://user:password@postgres:5432/attendance
      - REDIS_URL=redis://redis:6379

volumes:
  postgres_data:
```

## Backup Strategy

**Database Backup**
```bash
# PostgreSQL
pg_dump dbname > backup.sql

# Restore
psql dbname < backup.sql
```

**Media Files Backup**
```bash
# Sync to S3
aws s3 sync media/ s3://your-bucket/media/
```

## Health Checks

Create `attendance/health.py`:
```python
from django.http import JsonResponse
from django.db import connection

def health_check(request):
    try:
        connection.ensure_connection()
        return JsonResponse({'status': 'healthy'})
    except Exception as e:
        return JsonResponse({'status': 'unhealthy', 'error': str(e)}, status=500)
```

Add to URLs:
```python
path('health/', health_check),
```

---

**Need Help?** Refer to Django deployment documentation or open an issue.
