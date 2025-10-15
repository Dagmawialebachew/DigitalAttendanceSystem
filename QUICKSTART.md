pip install -r requirements.txt# ⚡ Quick Start Guide

Get the attendance system running in 5 minutes!

## Prerequisites

- Python 3.8 or higher
- Redis server (for real-time features)

## Installation Steps

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run Database Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 3. Create Demo Data

```bash
python setup.py
```

This creates:
- 1 Admin account
- 1 Teacher account
- 5 Student accounts
- 2 Demo courses
- 5 Achievement badges

### 4. Start Redis

**Option A: Using Docker**
```bash
docker run -d -p 6379:6379 redis:alpine
```

**Option B: System Installation**
```bash
# Ubuntu/Debian
sudo apt-get install redis-server
redis-server

# macOS
brew install redis
redis-server

# Windows
# Download from: https://redis.io/download
```

### 5. Start Django Server

```bash
python manage.py runserver
```

### 6. Access the Application

Open your browser and go to:
```
http://localhost:8000
```

## Login Credentials

### Teacher Account
```
Email: teacher@example.com
Password: password
```

### Student Accounts
```
Email: alice@example.com (or bob, charlie, diana, eve)
Password: password
```

### Admin Account
```
Email: admin@example.com
Password: password
```

## Quick Tour

### As a Teacher

1. **Login** with teacher credentials
2. Click **"Start Session"** on any course card
3. Set duration (default: 10 seconds)
4. **Display the 6-digit code** to students
5. Watch **real-time updates** as students submit
6. **End session** when done
7. **Export to CSV** for records

### As a Student

1. **Login** with student credentials
2. See **active sessions** with codes
3. **Tap to submit** when code appears
4. **Enter code** quickly (you have 10 seconds!)
5. Get **instant feedback** and earn points
6. Check **gamification** tab for badges and streaks

## Features to Try

### Real-time Updates
- Open teacher dashboard in one browser
- Open student view in another
- Submit attendance and watch live updates!

### Gamification
- Submit attendance to earn **10 points**
- Attend multiple days for **streak bonuses**
- Unlock **badges** as you progress

### Dark Mode
- Click the **moon/sun icon** in top-right
- Switches between light and dark themes
- Preference saved automatically

### PWA Features
- On mobile, tap "Add to Home Screen"
- App works like a native mobile app
- Bottom navigation for easy access

## Common Issues

### "Redis connection failed"
**Solution:** Make sure Redis is running
```bash
redis-server
```

### "No module named 'django'"
**Solution:** Install dependencies
```bash
pip install -r requirements.txt
```

### "Port 8000 already in use"
**Solution:** Use a different port
```bash
python manage.py runserver 8080
```

### Email not sending
**Solution:** Check console output. By default, emails are printed to console. To send real emails, configure SMTP in `.env`

## Development Tips

### Create Custom Users
```bash
python manage.py createsuperuser
```

### Django Shell
```bash
python manage.py shell
```

### View Logs
```bash
# Watch server logs in terminal
```

### Database GUI
```bash
# Install DB Browser for SQLite
# Open db.sqlite3
```

## What's Next?

1. ✅ **Explore Analytics** - View attendance trends
2. ✅ **Try Manual Override** - Add students manually
3. ✅ **Test Notifications** - Real-time alerts
4. ✅ **Export Data** - Download CSV reports
5. ✅ **Customize Settings** - Modify duration, etc.

## API Testing

### Start a Session (Teacher)
1. Login as teacher
2. Go to dashboard
3. Click "Start Session"

### Submit Attendance (Student)
1. Login as student
2. See active session
3. Enter code within 10 seconds

### View Analytics
1. Login as teacher
2. Click "Analytics" in bottom nav
3. Select course to view trends

## Mobile Testing

1. Open on mobile device
2. Use same network as server
3. Access: `http://your-ip:8000`
4. Add to home screen
5. Experience native-like app!

## Production Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for complete production setup guide.

---

**Need Help?** Check [README.md](README.md) for detailed documentation.

**Enjoy your modern attendance system! 🎓✨**
