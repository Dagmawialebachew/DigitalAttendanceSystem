from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, TeacherProfile, StudentProfile, Course, AttendanceSession,
    AttendanceEntry, InvalidAttempt, GamificationPoints, Badge,
    StudentBadge, Notification
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'first_name', 'last_name', 'role', 'is_active']
    list_filter = ['role', 'is_active', 'is_staff']
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'phone', 'avatar')}),
        ('Permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'role', 'first_name', 'last_name'),
        }),
    )
    search_fields = ['email', 'first_name', 'last_name']
    ordering = ['email']


@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'employee_id', 'department', 'subject']
    search_fields = ['user__email', 'employee_id', 'department']


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'student_id', 'department', 'year', 'section']
    list_filter = ['year', 'department']
    search_fields = ['user__email', 'student_id']


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'teacher', 'created_at']
    search_fields = ['code', 'name', 'teacher__email']
    filter_horizontal = ['students']


@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    list_display = ['code', 'course', 'teacher', 'start_time', 'status']
    list_filter = ['status', 'start_time']
    search_fields = ['code', 'course__name', 'teacher__email']


@admin.register(AttendanceEntry)
class AttendanceEntryAdmin(admin.ModelAdmin):
    list_display = ['student', 'session', 'timestamp', 'is_valid', 'manually_added']
    list_filter = ['is_valid', 'manually_added', 'timestamp']
    search_fields = ['student__email', 'session__code']


@admin.register(InvalidAttempt)
class InvalidAttemptAdmin(admin.ModelAdmin):
    list_display = ['student', 'session', 'timestamp', 'reason']
    list_filter = ['timestamp', 'reason']
    search_fields = ['student__email', 'session__code']


@admin.register(GamificationPoints)
class GamificationPointsAdmin(admin.ModelAdmin):
    list_display = ['student', 'total_points', 'streak_days', 'last_attendance_date']
    search_fields = ['student__email']


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ['name', 'badge_type', 'required_points', 'required_streak']
    list_filter = ['badge_type']


@admin.register(StudentBadge)
class StudentBadgeAdmin(admin.ModelAdmin):
    list_display = ['student', 'badge', 'earned_at']
    search_fields = ['student__email', 'badge__name']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'notification_type', 'title', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['user__email', 'title']
