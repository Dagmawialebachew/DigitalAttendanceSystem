from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
import random
import string
import re


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('admin', 'Admin'),
    )

    username = None
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')
    phone = models.CharField(max_length=20, blank=True, null=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        permissions = [
            ('can_start_session', 'Can start attendance session'),
            ('can_override_attendance', 'Can override attendance'),
            ('can_view_analytics', 'Can view analytics'),
        ]

    def __str__(self):
        return f"{self.get_full_name()} ({self.role})"

    @property
    def is_student(self):
        return self.role == 'student'

    @property
    def is_teacher(self):
        return self.role == 'teacher'

    @property
    def is_admin_role(self):
        return self.role == 'admin'


class TeacherProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile')
    department = models.CharField(max_length=100, blank=True)
    subject = models.CharField(max_length=100, blank=True)
    employee_id = models.CharField(max_length=4, unique=True, blank=True)
    bio = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if not self.employee_id:
            # Generate a random 4-digit employee_id
            while True:
                code = ''.join(random.choices(string.digits, k=4))
                if not TeacherProfile.objects.filter(employee_id=code).exists():
                    self.employee_id = code
                    break
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Teacher: {self.user.get_full_name()}"


class StudentProfile(models.Model):
    UGR_REGEX = r'^UGR/\d{4}/\d{2}$'

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    student_id = models.CharField(max_length=50, unique=True)
    department = models.CharField(max_length=100, blank=True)
    year = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], default=1)
    section = models.CharField(max_length=10, blank=True)

    def clean(self):
        if not re.match(self.UGR_REGEX, self.student_id):
            raise ValidationError("Student ID must be in UGR/****/** format")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Student: {self.user.get_full_name()}"


# ------------------- Remaining models unchanged -------------------
class Course(models.Model):
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=6, unique=True)  # short code
    description = models.TextField(blank=True)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='courses_taught')
    students = models.ManyToManyField(User, related_name='courses_enrolled', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.code} - {self.name}"

    def clean(self):
        if len(self.code) > 6:
            raise ValidationError("Course code must be 6 characters or less.")

class AttendanceSession(models.Model):
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('ended', 'Ended'),
        ('cancelled', 'Cancelled'),
    )

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='sessions')
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions_created')
    code = models.CharField(max_length=6, unique=True)
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    duration_seconds = models.IntegerField(default=10)

    class Meta:
        ordering = ['-start_time']

    def __str__(self):
        return f"{self.course.code} - {self.code} ({self.status})"

    @staticmethod
    def generate_code():
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))

    def is_valid(self):
        if self.status != 'active':
            return False
        time_elapsed = (timezone.now() - self.start_time).total_seconds()
        return time_elapsed <= self.duration_seconds

    def end_session(self):
        self.status = 'ended'
        self.end_time = timezone.now()
        self.save()


class AttendanceEntry(models.Model):
    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, related_name='entries')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendance_entries')
    timestamp = models.DateTimeField(auto_now_add=True)
    code_submitted = models.CharField(max_length=6)
    is_valid = models.BooleanField(default=False)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device_info = models.TextField(blank=True)
    manually_added = models.BooleanField(default=False)
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='manual_entries')

    class Meta:
        unique_together = ['session', 'student']
        ordering = ['-timestamp']

    def __str__(self):
        status = "Valid" if self.is_valid else "Invalid"
        return f"{self.student.get_full_name()} - {self.session.code} ({status})"


class InvalidAttempt(models.Model):
    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, related_name='invalid_attempts')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='invalid_attempts')
    code_submitted = models.CharField(max_length=6)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device_info = models.TextField(blank=True)
    reason = models.CharField(max_length=100)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.student.get_full_name()} - Invalid: {self.reason}"


class GamificationPoints(models.Model):
    student = models.OneToOneField(User, on_delete=models.CASCADE, related_name='gamification_points')
    total_points = models.IntegerField(default=0)
    streak_days = models.IntegerField(default=0)
    last_attendance_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.student.get_full_name()} - {self.total_points} points"

    def add_points(self, points):
        self.total_points += points

        today = timezone.now().date()
        if self.last_attendance_date:
            days_diff = (today - self.last_attendance_date).days
            if days_diff == 1:
                self.streak_days += 1
            elif days_diff > 1:
                self.streak_days = 1
        else:
            self.streak_days = 1

        self.last_attendance_date = today
        self.save()


class Badge(models.Model):
    BADGE_TYPES = (
        ('bronze', 'Bronze'),
        ('silver', 'Silver'),
        ('gold', 'Gold'),
        ('platinum', 'Platinum'),
    )

    name = models.CharField(max_length=100)
    description = models.TextField()
    badge_type = models.CharField(max_length=10, choices=BADGE_TYPES)
    icon = models.CharField(max_length=50, default='🏆')
    required_points = models.IntegerField(default=0)
    required_streak = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.name} ({self.badge_type})"


class StudentBadge(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='badges')
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE)
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['student', 'badge']
        ordering = ['-earned_at']

    def __str__(self):
        return f"{self.student.get_full_name()} - {self.badge.name}"


class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('session_started', 'Session Started'),
        ('attendance_marked', 'Attendance Marked'),
        ('late_warning', 'Late Warning'),
        ('absent_alert', 'Absent Alert'),
        ('badge_earned', 'Badge Earned'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    link = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.title}"
