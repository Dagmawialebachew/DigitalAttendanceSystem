from django.shortcuts import render
from django.urls import path
from . import views, pwa_views

urlpatterns = [
    # ------------------ 🔐 AUTH ------------------
    path('', views.LoginView.as_view(), name='login'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('register/', views.RegisterView.as_view(), name='register'),


    # ------------------ 🧭 DASHBOARD ------------------
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),

    # ------------------ 🧑‍🏫 TEACHER ------------------
    path('teacher/', views.TeacherDashboardView.as_view(), name='teacher_dashboard'),
    path('teacher/start/<int:course_id>/', views.StartSessionView.as_view(), name='start_session'),
    path('teacher/session/<int:session_id>/', views.SessionDetailView.as_view(), name='session_detail'),
    path('teacher/session/<int:session_id>/end/', views.EndSessionView.as_view(), name='end_session'),
    path('teacher/session/<int:session_id>/override/', views.ManualOverrideView.as_view(), name='manual_override'),
    path('teacher/analytics/', views.AnalyticsView.as_view(), name='analytics'),
    path('teacher/export/<int:session_id>/', views.ExportAttendanceView.as_view(), name='export_attendance'),

    # ------------------ 🎓 STUDENT ------------------
    path('student/', views.StudentDashboardView.as_view(), name='student_dashboard'),
    path('student/submit/<int:session_id>/', views.SubmitAttendanceView.as_view(), name='submit_attendance'),
    path('student/history/', views.AttendanceHistoryView.as_view(), name='attendance_history'),
    path('student/gamification/', views.GamificationView.as_view(), name='gamification'),

    # ------------------ 👤 SHARED PROFILE & NOTIFICATIONS ------------------
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('notifications/', views.NotificationsView.as_view(), name='notifications'),
    path('notifications/<int:notification_id>/read/', views.MarkNotificationReadView.as_view(), name='mark_notification_read'),

    # ------------------ 🌐 PWA ------------------
    path('manifest.json', pwa_views.manifest, name='manifest'),
    path('sw.js', pwa_views.service_worker, name='service_worker'),
        path('add-course/', views.AddCourseView.as_view(), name='add_course'),

    # ------------------ 🚀 COMING SOON ------------------
    path('proximity/', lambda request: render(request, 'attendance/coming_soon.html'), name='proximity_view'),
    
    



    path('teacher/course/new/', views.CourseCreateView.as_view(), name='course_create'),
    path('teacher/course/<int:pk>/edit/', views.CourseUpdateView.as_view(), name='course_update'),
    path('teacher/course/<int:pk>/delete/', views.CourseDeleteView.as_view(), name='course_delete'),

    path('profile/edit/', views.TeacherProfileUpdateView.as_view(), name='profile_edit'),
    path('student/profile/', views.StudentProfileView.as_view(), name='student_profile'),
    path('student/profile/edit/', views.StudentProfileEditView.as_view(), name='student_profile_edit'),
    path('course/<int:course_id>/', views.CourseDetailView.as_view(), name='course_detail'),

    # ...
    
    # ... (Keep all existing student and PWA routes) ...

]
