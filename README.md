# 🎓 Modern Digital Attendance System

A production-ready, futuristic 10-second code attendance system built with Django and Tailwind CSS. Features real-time updates, gamification, PWA capabilities, and a native-app-like mobile experience.

## ✨ Features

### Core Functionality
- **10-Second Code System**: Ultra-fast attendance submission with auto-expiring codes
- **Real-time Updates**: WebSocket-powered live attendance tracking
- **Role-Based Access**: Separate interfaces for Students, Teachers, and Admins
- **Anti-Cheat Measures**: IP/device logging, duplicate prevention, invalid attempt tracking
- **Manual Override**: Teachers can manually mark attendance when needed

### Student Features
- **Instant Code Submission**: Auto-focus input with live countdown timer
- **Gamification**: Points, badges, and streak tracking
- **Attendance History**: Complete record with visual feedback
- **Real-time Notifications**: Instant alerts for sessions and achievements
- **Profile Dashboard**: View stats, badges, and points

### Teacher Features
- **Session Management**: Easy session creation with customizable duration
- **Live Dashboard**: Real-time attendance updates during sessions
- **Analytics**: Attendance trends, charts, and insights
- **Manual Override**: Add students manually when needed
- **Export Options**: CSV export for record-keeping
- **Email Recaps**: Automatic email summaries after each session

### Technical Highlights
- **Progressive Web App (PWA)**: Install as a mobile app
- **Bottom Navigation**: Native mobile app experience
- **Dark Mode**: System-wide theme toggle
- **Responsive Design**: Optimized for all devices
- **Modern UI**: Tailwind CSS with smooth animations
- **Real-time**: Django Channels with WebSocket support

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Redis (for WebSocket support)

### Installation

1. **Install Dependencies**
```bash
pip install -r requirements.txt
```

2. **Set Up Environment Variables**
```bash
# Create .env file (optional, has defaults)
SECRET_KEY=your-secret-key-here
DEBUG=True
REDIS_URL=redis://127.0.0.1:6379
```

3. **Run Migrations**
```bash
python manage.py makemigrations
python manage.py migrate
```

4. **Create Demo Data**
```bash
python setup.py
```

5. **Start Redis** (in a separate terminal)
```bash
redis-server
```

6. **Run Development Server**
```bash
python manage.py runserver
```

7. **Access the Application**
```
http://localhost:8000
```

## 👥 Demo Accounts

After running `setup.py`, use these credentials:

**Admin:**
- Email: `admin@example.com`
- Password: `password`

**Teacher:**
- Email: `teacher@example.com`
- Password: `password`

**Students:**
- Email: `alice@example.com` (or bob, charlie, diana, eve)
- Password: `password`

## 📱 How to Use

### For Teachers

1. **Login** with teacher credentials
2. **Select a Course** from your dashboard
3. **Start Session** and set duration (default: 10 seconds)
4. **Display Code** on screen for students
5. **Monitor Live** as students submit attendance
6. **End Session** when complete
7. **View Analytics** and export data

### For Students

1. **Login** with student credentials
2. **View Active Sessions** on dashboard
3. **Tap to Submit** when code appears
4. **Enter Code** quickly (10-second window)
5. **Get Instant Feedback** with points
6. **Track Progress** in gamification section

## 🏗️ Project Structure

```
attendance_system/
├── attendance/                 # Main app
│   ├── models.py              # Database models
│   ├── views.py               # View logic
│   ├── services.py            # Business logic
│   ├── consumers.py           # WebSocket consumers
│   ├── routing.py             # WebSocket routing
│   ├── admin.py               # Admin interface
│   └── pwa_views.py           # PWA manifest/SW
├── templates/
│   ├── base.html              # Base template with nav
│   └── attendance/
│       ├── login.html
│       ├── teacher/           # Teacher templates
│       ├── student/           # Student templates
│       └── email/             # Email templates
├── attendance_system/
│   ├── settings.py            # Django settings
│   ├── urls.py                # URL configuration
│   ├── asgi.py                # ASGI config (WebSocket)
│   └── wsgi.py                # WSGI config
├── manage.py
├── setup.py                   # Demo data script
└── requirements.txt
```

## 🎮 Gamification System

Students earn:
- **10 points** per attendance
- **Badges** for milestones:
  - 🥉 First Timer (10 points)
  - 🥈 Regular (100 points)
  - 🥇 Dedicated (500 points)
  - 🔥 Streak Master (7 days)
  - 💎 Perfect Month (30 days)

## 🔒 Security Features

- **Session-based Authentication**
- **CSRF Protection**
- **Role-based Permissions**
- **IP Address Logging**
- **Device Info Tracking**
- **Duplicate Prevention**
- **Invalid Attempt Logging**

## 🌐 Real-time Features

### WebSocket Channels
- **Attendance Updates**: Live student submissions
- **Notifications**: Instant alerts for all users
- **Session Status**: Real-time session end notifications

### Broadcasting
- Teachers see live attendance updates
- Students receive session start notifications
- Badge achievements trigger instant notifications

## 📊 Analytics

Teachers can view:
- Attendance percentage per session
- Trend analysis over time
- Student participation rates
- Visual charts and graphs

## 📧 Email Notifications

Automatic email recaps include:
- Session summary
- Present/absent counts
- Complete student lists
- Formatted HTML emails

## 🎨 UI/UX Features

- **Modern Design**: Sleek, futuristic interface
- **Smooth Animations**: Fade-in, pulse, shake effects
- **Color-coded Feedback**: Success (green), error (red)
- **Bottom Navigation**: Like native mobile apps
- **Glass Morphism**: Modern backdrop blur effects
- **Dark Mode**: Full theme support
- **Touch-optimized**: Perfect for mobile devices

## 🔧 Configuration

### Email Settings (in `.env`)
```bash
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=noreply@attendance.com
```

### Redis Settings
```bash
REDIS_URL=redis://127.0.0.1:6379
```

## 📦 Production Deployment

1. **Set DEBUG=False** in settings
2. **Configure proper SECRET_KEY**
3. **Set up production database** (PostgreSQL recommended)
4. **Configure Redis** for WebSocket
5. **Set up Daphne** or ASGI server
6. **Configure static files** serving
7. **Set up SSL** for HTTPS
8. **Configure email** backend

### Running with Daphne
```bash
daphne -b 0.0.0.0 -p 8000 attendance_system.asgi:application
```

## 🧪 Testing

Create test users:
```bash
python manage.py createsuperuser
```

Run Django shell:
```bash
python manage.py shell
```

## 🚧 Future Features (Coming Soon)

- ✅ Proximity Detection (Wi-Fi/Bluetooth)
- ✅ QR Code Integration
- ✅ Biometric Authentication
- ✅ Advanced Analytics Dashboard
- ✅ Mobile Apps (iOS/Android)
- ✅ Integration APIs
- ✅ Multi-language Support

## 📄 License

This project is open source and available for educational purposes.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📞 Support

For issues or questions, please open an issue on the project repository.

---

**Built with ❤️ using Django + Tailwind CSS**

*Modern. Fast. Secure. Gamified.*
