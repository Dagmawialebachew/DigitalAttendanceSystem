# 🔧 Troubleshooting Guide

Common issues and their solutions.

## Installation Issues

### "pip: command not found"
**Problem:** pip is not installed or not in PATH

**Solution:**
```bash
# Use python3 -m pip instead
python3 -m pip install -r requirements.txt

# Or install pip
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
python3 get-pip.py
```

### "ModuleNotFoundError: No module named 'django'"
**Problem:** Dependencies not installed

**Solution:**
```bash
pip install -r requirements.txt
```

### "Permission denied" when installing
**Problem:** Need admin privileges

**Solution:**
```bash
# Use --user flag
pip install --user -r requirements.txt

# Or use virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Database Issues

### "no such table: attendance_user"
**Problem:** Database migrations not run

**Solution:**
```bash
python manage.py makemigrations
python manage.py migrate
```

### "UNIQUE constraint failed"
**Problem:** Trying to create duplicate data

**Solution:**
```bash
# Delete database and start fresh
rm db.sqlite3
python manage.py migrate
python setup.py
```

### "table already exists"
**Problem:** Migration state mismatch

**Solution:**
```bash
# Reset migrations
rm db.sqlite3
rm attendance/migrations/0*.py
python manage.py makemigrations attendance
python manage.py migrate
```

## Redis Issues

### "Connection refused" or "Redis connection failed"
**Problem:** Redis server not running

**Solution:**
```bash
# Start Redis
redis-server

# Or with Docker
docker run -d -p 6379:6379 redis:alpine

# Check if Redis is running
redis-cli ping
# Should return: PONG
```

### "redis: command not found"
**Problem:** Redis not installed

**Solution:**
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install redis-server

# macOS
brew install redis

# Windows
# Download from: https://redis.io/download
# Or use Docker
```

### Redis on different port
**Problem:** Redis running on non-default port

**Solution:**
```bash
# Create .env file
echo "REDIS_URL=redis://127.0.0.1:6380" > .env
```

## WebSocket Issues

### WebSocket not connecting
**Problem:** Browser console shows WebSocket errors

**Solution:**
1. Ensure Redis is running
2. Check if port 8000 is accessible
3. Try with `ws://` instead of `wss://` in development
4. Check browser console for detailed error

### "WebSocket connection failed"
**Problem:** ASGI server not configured correctly

**Solution:**
```bash
# Ensure you're running Django 3.0+
pip install django>=5.0

# Restart the server
python manage.py runserver
```

## Server Issues

### "Port 8000 already in use"
**Problem:** Another process using port 8000

**Solution:**
```bash
# Use different port
python manage.py runserver 8080

# Or kill existing process
# Linux/Mac:
lsof -ti:8000 | xargs kill -9

# Windows:
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### "Address already in use"
**Problem:** Previous server instance still running

**Solution:**
```bash
# Linux/Mac
pkill -f runserver

# Windows
# Use Task Manager to end Python processes
```

### Static files not loading
**Problem:** Static files not collected

**Solution:**
```bash
python manage.py collectstatic --noinput
```

## Authentication Issues

### "Invalid email or password"
**Problem:** Wrong credentials or user not created

**Solution:**
```bash
# Run setup to create demo users
python setup.py

# Or create user manually
python manage.py createsuperuser
```

### Logged out unexpectedly
**Problem:** Session expired

**Solution:**
- Login again
- Check `SESSION_COOKIE_AGE` in settings.py
- Clear browser cookies and try again

### Can't access admin panel
**Problem:** User is not staff/superuser

**Solution:**
```bash
python manage.py shell
```
```python
from attendance.models import User
user = User.objects.get(email='your@email.com')
user.is_staff = True
user.is_superuser = True
user.save()
```

## Real-time Updates Not Working

### Attendance not updating live
**Problem:** WebSocket not connected

**Solution:**
1. Check Redis is running: `redis-cli ping`
2. Check browser console for WebSocket errors
3. Ensure channels is installed: `pip install channels channels-redis`
4. Restart Django server

### Notifications not appearing
**Problem:** WebSocket connection or consumer issue

**Solution:**
1. Open browser DevTools → Network tab
2. Look for WebSocket connection (WS)
3. Should show "101 Switching Protocols"
4. If not, check Redis and restart server

## Email Issues

### Emails not sending
**Problem:** Email backend not configured

**Solution:**
By default, emails print to console. To send real emails:

```bash
# Create .env file
cat > .env << EOF
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=noreply@yourdomain.com
EOF
```

**For Gmail:**
1. Enable 2-factor authentication
2. Generate app-specific password
3. Use that password in EMAIL_HOST_PASSWORD

## Session Code Issues

### "Session expired" immediately
**Problem:** Time sync or duration too short

**Solution:**
1. Check system time is correct
2. Increase duration when starting session
3. Check timezone in settings.py: `TIME_ZONE = 'UTC'`

### Code not validating
**Problem:** Case sensitivity or whitespace

**Solution:**
- Codes are automatically converted to uppercase
- Remove any spaces before/after code
- Ensure student is enrolled in the course

## UI/Display Issues

### Dark mode not working
**Problem:** LocalStorage not accessible

**Solution:**
- Clear browser cache
- Check browser allows localStorage
- Try in incognito mode to test

### Bottom navigation not showing
**Problem:** CSS not loading or not logged in

**Solution:**
1. Login to see navigation
2. Hard refresh (Ctrl+Shift+R)
3. Check browser console for errors

### Animations not smooth
**Problem:** Browser or device performance

**Solution:**
- Try in Chrome/Firefox
- Close other tabs
- Update graphics drivers
- Disable animations in base.html if needed

## PWA Issues

### Can't install as app
**Problem:** Not using HTTPS or missing files

**Solution:**
- PWA requires HTTPS (except localhost)
- Ensure manifest.json is accessible
- Check service worker registration in console

### Icon not appearing
**Problem:** Icons not created

**Solution:**
1. Generate icons at https://www.pwabuilder.com/imageGenerator
2. Save as `icon-192x192.png` and `icon-512x512.png`
3. Place in `static/icons/` directory

## Performance Issues

### Slow page loads
**Problem:** Database queries or missing indexes

**Solution:**
```bash
# Run with query logging to identify slow queries
# Add to settings.py:
LOGGING = {
    'version': 1,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

### Memory issues
**Problem:** Redis or Django consuming too much memory

**Solution:**
```bash
# Configure Redis maxmemory
redis-cli CONFIG SET maxmemory 256mb
redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

## Production Issues

### DEBUG=False shows errors
**Problem:** Static files not configured

**Solution:**
```bash
# Collect static files
python manage.py collectstatic

# Use WhiteNoise for static files
pip install whitenoise
# Add to MIDDLEWARE in settings.py
```

### 502 Bad Gateway
**Problem:** ASGI server not running

**Solution:**
```bash
# Restart Daphne
daphne -b 0.0.0.0 -p 8000 attendance_system.asgi:application
```

## Getting Help

Still stuck? Try these:

1. **Check Django Logs**
   - Look at server console output
   - Enable DEBUG=True temporarily

2. **Browser DevTools**
   - Console tab for JS errors
   - Network tab for failed requests
   - Application tab for storage issues

3. **Django Shell**
   ```bash
   python manage.py shell
   ```
   Test models and queries directly

4. **Database Inspection**
   ```bash
   python manage.py dbshell
   ```
   Examine data directly

5. **Fresh Start**
   ```bash
   # Nuclear option: start completely fresh
   rm -rf db.sqlite3
   rm -rf attendance/migrations/0*.py
   python manage.py makemigrations
   python manage.py migrate
   python setup.py
   ```

## Common Error Messages

| Error | Likely Cause | Solution |
|-------|--------------|----------|
| "CSRF verification failed" | Cookie issues | Clear cookies, ensure CSRF token in form |
| "404 Not Found" | URL pattern mismatch | Check urls.py patterns |
| "500 Internal Server Error" | Python exception | Check server console for traceback |
| "Connection refused" | Service not running | Start Redis/Django |
| "Permission denied" | File/directory permissions | Check file ownership |
| "Module not found" | Missing dependency | Run `pip install -r requirements.txt` |

---

**Still need help?**
- Check Django documentation: https://docs.djangoproject.com/
- Check Channels documentation: https://channels.readthedocs.io/
- Review server logs carefully
- Search error messages online
