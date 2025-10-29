import datetime
import json
import re
from django.utils.encoding import smart_str
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView, ListView, DetailView, UpdateView, CreateView, DeleteView
from django.db.models import Q
from datetime import timedelta
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db.models import Prefetch
from django.http import HttpRequest
from django.db.models import Prefetch, Count, Q
from django.db.models.functions import TruncMonth
import csv
from .models import (
    User, Course, AttendanceSession, AttendanceEntry,
    GamificationPoints, Badge, StudentBadge, Notification
)
from .services import AttendanceService


# --- Helper Mixins ---
class TeacherRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and (
            self.request.user.is_teacher or self.request.user.is_admin_role
        )


class StudentRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_student
# -----------------------
# REGISTER VIEW
# -----------------------
class RegisterView(View):
    template_name = 'attendance/register.html'

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        # 1. Normalize and Retrieve Data
        ugr_raw = request.POST.get('ugr')
        ugr = ugr_raw.upper() if ugr_raw else ''
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        
        context = {'ugr': ugr_raw}  # Use the raw value for re-populating the form on error

        # 2. Validate UGR format
        if not re.match(r'^UGR/\d{4}/\d{2}$', ugr):
            messages.error(request, "Invalid UGR format. Example: UGR/8286/17")
            return render(request, self.template_name, context)

        # 3. Check password match
        if password != confirm_password:
            messages.error(request, "Passwords do not match")
            return render(request, self.template_name, context)

        # 4. Check for existing StudentProfile
        if StudentProfile.objects.filter(student_id=ugr).exists():
            messages.error(request, f"A student profile with ID {ugr} already exists.")
            return render(request, self.template_name, context)

        # 5. Check if User exists
        email = f"{ugr.lower()}@gmail.com"
        try:
            user, user_created = User.objects.get_or_create(
                email=email,
                defaults={'role': 'student', 'email': email}
            )
            
            if user_created:
                user.set_password(password)
                user.save()
                messages.success(request, "Account created successfully. Welcome!")
            else:
                messages.info(request, "Account already exists. You can continue.")

            # 6. Ensure StudentProfile exists
            student_profile, profile_created = StudentProfile.objects.get_or_create(
                user=user, 
                defaults={'student_id': ugr}
            )

            # Redirect to home page instead of login
            login(request, user)
            return redirect('dashboard')  # <-- Change this to your actual home page URL name

        except Exception as e:
            messages.error(request, f"An unexpected error occurred: {e}")
            return render(request, self.template_name, context)

# -----------------------
# LOGIN VIEW
# -----------------------
@method_decorator(csrf_exempt, name='dispatch')
class LoginView(View):
    template_name = 'attendance/login.html'

    def get(self, request):
        if request.user.is_authenticated:
            return self.redirect_by_role(request.user)

        email_or_ugr = request.session.get('login_email_or_ugr', '')
        return render(request, self.template_name, {'email_or_ugr': email_or_ugr})

    def post(self, request):
        login_input = request.POST.get('email_or_ugr', '').strip()  # can be email or UGR
        password = request.POST.get('password')

        # Store input temporarily
        request.session['login_email_or_ugr'] = login_input

        # Authenticate by email first
        user = authenticate(request, email=login_input, password=password)

        # If not found by email, check if it's a student UGR
        if not user:
            try:
                student_profile = StudentProfile.objects.get(student_id=login_input)
                user = student_profile.user
                # Ensure StudentProfile exists
                if not hasattr(user, 'student_profile'):
                    StudentProfile.objects.create(user=user, student_id=login_input)
                # Authenticate using email
                user = authenticate(request, email=user.email, password=password)
            except StudentProfile.DoesNotExist:
                user = None

        if user:
            # Ensure StudentProfile exists for students
            if user.role == 'student' and not hasattr(user, 'student_profile'):
                StudentProfile.objects.create(user=user, student_id=login_input)

            # Clear session input
            request.session.pop('login_email_or_ugr', None)

            login(request, user)
            return self.redirect_by_role(user)

        messages.error(request, 'Invalid email/UGR or password')
        return render(request, self.template_name, {'email_or_ugr': login_input})

    def redirect_by_role(self, user):
        """Redirect user based on their role."""
        if user.role == 'student':
            return redirect('student_dashboard')
        elif user.role == 'teacher':
            return redirect('teacher_dashboard')  # create this URL
        elif user.role == 'admin':
            return redirect('admin_dashboard')  # create this URL
        else:
            return redirect('login')
class LogoutView(LoginRequiredMixin, View):
    def get(self, request):
        logout(request)
        return redirect('login')


class DashboardView(LoginRequiredMixin, View):
    def get(self, request):
        if request.user.is_teacher or request.user.is_admin_role:
            return redirect('teacher_dashboard')
        return redirect('student_dashboard')


# --- Teacher Views ---
class TeacherDashboardView(LoginRequiredMixin, TeacherRequiredMixin, TemplateView):
    template_name = 'attendance/teacher/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['courses'] = Course.objects.filter(teacher=self.request.user).prefetch_related('students')
        context['recent_sessions'] = AttendanceSession.objects.filter(teacher=self.request.user)[:10]
        return context


class StartSessionView(LoginRequiredMixin, TeacherRequiredMixin, View):
    template_name = 'attendance/teacher/start_session.html'

    def get(self, request, course_id):
        course = get_object_or_404(Course, id=course_id, teacher=request.user)
        return render(request, self.template_name, {'course': course})

    def post(self, request, course_id):
        course = get_object_or_404(Course, id=course_id, teacher=request.user)
        duration = int(request.POST.get('duration', 10))
        session = AttendanceService.create_session(course, request.user, duration)
        return redirect('session_detail', session_id=session.id)


class SessionDetailView(LoginRequiredMixin, TeacherRequiredMixin, TemplateView):
    template_name = 'attendance/teacher/session_detail.html'

    def get_context_data(self, **kwargs):
        session = get_object_or_404(AttendanceSession, id=kwargs['session_id'], teacher=self.request.user)
        entries = AttendanceEntry.objects.filter(session=session, is_valid=True).select_related('student')
        return {
            'session': session,
            'entries': entries,
            'total_students': session.course.students.count(),
            'present_count': entries.count(),
        }


class EndSessionView(LoginRequiredMixin, TeacherRequiredMixin, View):
    def post(self, request, session_id):
        session = get_object_or_404(AttendanceSession, id=session_id, teacher=request.user)
        AttendanceService.end_session(session)
        messages.success(request, 'Session ended successfully')
        return redirect('session_detail', session_id=session.id)


class ManualOverrideView(LoginRequiredMixin, TeacherRequiredMixin, View):
    def post(self, request, session_id):
        session = get_object_or_404(AttendanceSession, id=session_id, teacher=request.user)
        student_id = request.POST.get('student_id')
        student = get_object_or_404(User, id=student_id, role='student')

        AttendanceService.manual_override(session, student, request.user)
        messages.success(request, f'Manually marked attendance for {student.get_full_name()}')

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})

        return redirect('session_detail', session_id=session.id)


class AnalyticsView(LoginRequiredMixin, TeacherRequiredMixin, View):
    """
    Handles analytics with:
    - Course tabs
    - Date filter tabs (Today, Week, Month, All)
    - Custom date picker
    - "5 recent" fallback for 'Today'
    """
    template_name = 'attendance/teacher/analytics.html'
    partial_template_name = 'attendance/teacher/_analytics_data.html'

    def get(self, request: HttpRequest) -> HttpResponse:
        teacher = request.user
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
        today = timezone.localdate()
        
        # 1. Get all courses for the tabs
        courses_queryset = Course.objects.filter(teacher=teacher).order_by('name')

        # 2. Get filters. Default to '0' (All Courses) and 'today'.
        course_id = request.GET.get('course', '0')
        # This one parameter handles 'today', 'week', 'month', 'all', OR a date string
        date_filter = request.GET.get('date_filter', 'today') 

        # 3. Get the analytics data
        context = self._get_analytics_data(
            teacher, 
            courses_queryset, 
            course_id, 
            date_filter
        )
        
        # 4. Add data for the main page template
        context['courses'] = courses_queryset
        context['today_iso'] = today.isoformat() 
        
        # Pass the date_filter back for active tab styling
        context['selected_date_filter'] = context.get('selected_date_filter', date_filter)

        # 5. Render
        if is_ajax:
            return render(request, self.partial_template_name, context)
        
        return render(request, self.template_name, context)

    def _get_analytics_data(self, teacher, courses_queryset, course_id, date_filter):
        
        selected_course = None
        courses_to_analyze = None
        is_master_view = (course_id == '0')

        if is_master_view:
            courses_to_analyze = courses_queryset
        else:
            selected_course = get_object_or_404(courses_queryset, id=course_id)
            courses_to_analyze = Course.objects.filter(pk=selected_course.pk)
        
        # --- 1. Student Counts (Unchanged) ---
        student_counts_map = {
            c['id']: c['student_count'] 
            for c in courses_to_analyze.annotate(student_count=Count('students'))
                                    .values('id', 'student_count')
        }

        # --- 2. Smart Date Filtering ---
        today = timezone.localdate()
        date_filter_q = Q() # Default to 'all'
        parsed_date_iso = None # For display
        is_today_query = False

        if date_filter == 'today':
            date_filter_q = Q(start_time__date=today)
            parsed_date_iso = today.isoformat()
            is_today_query = True
        elif date_filter == 'week':
            start_of_week = today - datetime.timedelta(days=today.weekday())
            date_filter_q = Q(start_time__date__gte=start_of_week)
            parsed_date_iso = f"Week of {start_of_week.isoformat()}"
        elif date_filter == 'month':
            start_of_month = today.replace(day=1)
            date_filter_q = Q(start_time__date__gte=start_of_month)
            parsed_date_iso = f"Month of {start_of_month.isoformat()}"
        elif date_filter == 'all':
            parsed_date_iso = "All Time"
            pass # date_filter_q is already empty Q()
        else:
            # Try to parse it as a custom date string
            try:
                parsed_date = datetime.date.fromisoformat(date_filter)
                date_filter_q = Q(start_time__date=parsed_date)
                parsed_date_iso = parsed_date.isoformat()
                if parsed_date == today:
                    is_today_query = True
            except (ValueError, TypeError):
                # Fallback to 'today' if date is invalid
                date_filter_q = Q(start_time__date=today)
                parsed_date_iso = today.isoformat()
                date_filter = 'today' # Correct the filter for the template
                is_today_query = True
                
        # --- 3. Get Base Session Query (Unchanged) ---
        sessions_base_qs = AttendanceSession.objects.filter(
            course__in=courses_to_analyze, 
            status='ended'
        )

        # 4. Run Primary Query
        sessions = (
            sessions_base_qs.filter(date_filter_q) # Apply the smart filter
            .annotate(
                present_count=Count('entries', filter=Q(entries__is_valid=True))
            )
            .select_related('course')
            .order_by('-start_time')
        )

        # 5. Process Primary Data (Unchanged)
        attendance_data = []
        all_percentages = []
        for session in sessions:
            # ... (Same data processing logic) ...
            total_students = student_counts_map.get(session.course.id, 0)
            present_count = session.present_count
            percentage = min((present_count / total_students * 100) if total_students > 0 else 0, 100)
            all_percentages.append(percentage)
            attendance_data.append({ 'date': session.start_time.strftime('%Y-%m-%d'), 'course_name': session.course.code, 'present': present_count, 'total': total_students, 'percentage': percentage,     'course_id': session.course.id })

        # 6. Calculate Primary Stats (Unchanged)
        average_attendance = sum(all_percentages) / len(all_percentages) if all_percentages else 0
        total_sessions_count = len(attendance_data)
        total_students_count = 0 # ... (Same student count logic) ...
        if is_master_view:
            total_students_count = User.objects.filter(role='student', courses_enrolled__in=courses_to_analyze).distinct().count()
        elif selected_course:
            total_students_count = student_counts_map.get(selected_course.id, 0)

        # 7. FALLBACK LOGIC (Only for 'today' queries)
        is_fallback_view = False
        if not attendance_data and is_today_query:
            is_fallback_view = True
            sessions_fallback = (
                sessions_base_qs
                .annotate(present_count=Count('entries', filter=Q(entries__is_valid=True)))
                .select_related('course')
                .order_by('-start_time')
            )[:5] # Get 5 most recent
            
            # Re-process data *just for the list*
            attendance_data = []
            for session in sessions_fallback:
                # ... (Same processing logic as in step 5) ...
                total_students = student_counts_map.get(session.course.id, 0)
                present_count = session.present_count
                percentage = min((present_count / total_students * 100) if total_students > 0 else 0, 100)
                attendance_data.append({ 'date': session.start_time.strftime('%Y-%m-%d'), 'course_name': session.course.code, 'present': present_count, 'total': total_students, 'percentage': percentage, 'course_id': session.course.id })

        # 8. Chart Data
        # Title says "Last 30", so let's slice it to 30
        chart_data_list = attendance_data[:30]
        chart_labels = [d['date'] for d in reversed(chart_data_list)]
        chart_data_pct = [d['percentage'] for d in reversed(chart_data_list)]
        print(chart_labels, chart_data_pct, "--- chart data ---", chart_data_list)

        return {
            'selected_course_id': course_id,
            'selected_date_filter': date_filter, # This is key: 'today', 'week', or 'YYYY-MM-DD'
            'display_date_range': parsed_date_iso, # For titles
            'is_master_view': is_master_view,
            'average_attendance': average_attendance,
            'total_sessions': total_sessions_count,
            'total_students': total_students_count,
            'attendance_data': attendance_data,
            'has_data': bool(attendance_data),
            'is_fallback_view': is_fallback_view,
            'chart_labels': json.dumps(chart_labels),
            'chart_data_pct': json.dumps(chart_data_pct, cls=DjangoJSONEncoder),
        }




class ExportAttendanceView(LoginRequiredMixin, TeacherRequiredMixin, View):
    def get(self, request, session_id):
        session = get_object_or_404(
            AttendanceSession, id=session_id, teacher=request.user
        )
        entries = AttendanceEntry.objects.filter(
            session=session, is_valid=True
        ).select_related('student')

        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = (
            f'attachment; filename="attendance_{session.code}.csv"'
        )

        writer = csv.writer(response)
        writer.writerow([
            'Student Name',
            'Student ID',
            'Date',
            'Time',
            'Manually Added'
        ])

        for e in entries:
            # Format date and time separately
            date_str = e.timestamp.strftime('%a, %b %d, %Y')   # Mon, Oct 05, 2025
            time_str = e.timestamp.strftime('%I:%M %p')        # 12:00 PM

            writer.writerow([
                smart_str(e.student.get_full_name()),
                smart_str(getattr(e.student.student_profile, 'student_id', '')),
                date_str,
                time_str,
                'Yes' if e.manually_added else 'No'
            ])

        return response
# In attendance/views.py

import datetime
from django.shortcuts import render, get_object_or_404
from django.views.generic import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q, Max, F
from django.http import JsonResponse

# Assuming these are your necessary custom mixins and models
# from .mixins import TeacherRequiredMixin 
# from .models import Course, AttendanceSession, AttendanceEntry, User # <-- Ensure User is imported

class DailySessionDetailView(LoginRequiredMixin, TeacherRequiredMixin, View):
    """
    Displays all students and their attendance status (aggregated) for a single day.
    Also handles the AJAX request for the student roster.
    """
    template_name = 'attendance/teacher/daily_detail.html'
    
    def get(self, request, course_id, date_str):
        try:
            target_date = datetime.date.fromisoformat(date_str)
        except ValueError:
            return render(request, 'error_page.html', {'message': 'Invalid date format.'}, status=400)
        
        teacher = request.user
        course = get_object_or_404(Course, pk=course_id, teacher=teacher)
        
        # 1. Get all sessions for the day/course
        sessions = AttendanceSession.objects.filter(
            course=course,
            start_time__date=target_date,
            status='ended'
        ).order_by('start_time')
        
        # 2. Get all students in the course
        all_students = course.students.all().order_by('last_name', 'first_name')
        
        # --- Roster Processing (needed for both initial load and AJAX) ---
        roster = self._get_daily_roster(all_students, sessions)
        roster_json = json.dumps(roster, cls=DjangoJSONEncoder)

        # Handle AJAX request for the live data update
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'roster': roster_json})

        # Initial GET request (Full page render)
        context = {
            'course': course,
            'target_date': target_date,
            'initial_roster_json': roster_json, # Pass processed data as JSON for initial page load
            'has_sessions': sessions.exists(),
        }
        
        return render(request, self.template_name, context)

    def _get_daily_roster(self, all_students, sessions):
        # Maps student ID to their status in the LAST session of the day
        student_status_map = {} 
        
        # 1. If there are sessions, find the ID of the LATEST session
        latest_session_id = sessions.aggregate(Max('id'))['id__max']
        
        if latest_session_id:
            # 2. Find all entries for ALL sessions on this day
            all_entries = AttendanceEntry.objects.filter(
                session__in=sessions
            ).select_related('student', 'session')
            
            # Use a dict to track the status, prioritizing the latest session
            status_tracking = {} # { student_id: { status: 'P'/'A', session_time: datetime } }
            
            for entry in all_entries:
                student_id = entry.student_id
                entry_time = entry.session.start_time
                status = 'P' if entry.is_valid else 'A'
                
                # Update status only if it's the first record or a later session
                if student_id not in status_tracking or entry_time > status_tracking[student_id]['session_time']:
                    status_tracking[student_id] = {
                        'status': status,
                        'session_time': entry_time
                    }

            # 3. Compile the final roster using the tracking data
            roster = []
            for student in all_students:
                final_status = status_tracking.get(student.id, {'status': 'A'})['status']  # Default to Absent
                
                # Try to build name, fallback to studentprofile.student_id
                full_name = f"{student.first_name or ''} {student.last_name or ''}".strip()
                if not full_name:
                    try:
                        full_name = student.student_profile.student_id
                    except AttributeError:
                        full_name = str(student.id)  # fallback to DB ID if profile missing entirely

                roster.append({
                    'id': student.id,
                    'name': full_name,
                    'status': final_status,
                })

        else:
                # No sessions means everyone is Absent (by default)
                roster = [{
                    'id': student.id,
                    'name': (
                        f"{student.first_name or ''} {student.last_name or ''}".strip() or
                        getattr(student.student_profile, 'student_id', str(student.id))
                    ),
                    'status': 'A'
                } for student in all_students]

        print(roster, "--- daily roster ---")
            
        return roster

# --- Student Views ---
class StudentDashboardView(LoginRequiredMixin, StudentRequiredMixin, TemplateView):
    template_name = 'attendance/student/dashboard.html'

    def get_context_data(self, **kwargs):
        user = self.request.user
        context = super().get_context_data(**kwargs)

        # --- Attendance Data ---
        active_sessions = AttendanceSession.objects.filter(
            course__students=user,
            status='active',
            start_time__gte=timezone.now() - timedelta(seconds=30)
        )
        recent_entries = AttendanceEntry.objects.filter(student=user, is_valid=True)[:10]

        # --- Gamification ---
        gamification, _ = GamificationPoints.objects.get_or_create(student=user)
        recent_badges = StudentBadge.objects.filter(student=user)[:3]

        # --- Profile check ---
        profile_filled = bool(user.first_name and user.last_name)
        context['profile_filled'] = profile_filled

        # --- Courses ---
        courses = user.courses_enrolled.all()
        context['courses'] = courses
        context['no_courses'] = not courses.exists()

        context.update({
            'active_sessions': active_sessions,
            'recent_entries': recent_entries,
            'gamification': gamification,
            'recent_badges': recent_badges,
        })

        return context

    def post(self, request, *args, **kwargs):
        """
        Handle adding courses by code.
        """
        user = request.user
        course_code = request.POST.get('course_code', '').strip().upper()

        if course_code:
            try:
                course = Course.objects.get(code=course_code)
                user.courses_enrolled.add(course)
                messages.success(request, f"Successfully added course: {course.name}")
            except Course.DoesNotExist:
                messages.error(request, "Invalid course code. Please check and try again.")

        return redirect('student_dashboard')


class SubmitAttendanceView(LoginRequiredMixin, StudentRequiredMixin, View):
    template_name = 'attendance/student/submit.html'

    def get(self, request, session_id):
        # Fetch active session
        session = get_object_or_404(AttendanceSession, id=session_id, status='active')

        if not session.is_valid():
            messages.error(request, "This session is no longer valid.")
            return redirect('student_dashboard')

        context = {
            'session': session,
            'is_valid': True
        }
        return render(request, self.template_name, context)

    def post(self, request, session_id):
        # Fetch active session
        session = get_object_or_404(AttendanceSession, id=session_id, status='active')

        # Ensure student is enrolled
        if request.user not in session.course.students.all():
            messages.error(request, 'You are not enrolled in this course')
            return redirect('student_dashboard')

        # Collect data
        code = request.POST.get('code', '').upper()
        ip = request.META.get('REMOTE_ADDR')
        device = request.META.get('HTTP_USER_AGENT', '')

        # Submit attendance using AttendanceService
        success, msg, entry = AttendanceService.submit_attendance(session, request.user, code, ip, device)

        # Broadcast the new entry if successful
        if success and entry:
            AttendanceService.broadcast_update(session)

        # Return JSON for AJAX or redirect with messages
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': success, 'message': msg})

        messages.success(request, msg) if success else messages.error(request, msg)
        return redirect('student_dashboard')
class AttendanceHistoryView(LoginRequiredMixin, StudentRequiredMixin, TemplateView):
    template_name = 'attendance/student/history.html'

    def get_context_data(self, **kwargs):
        entries = AttendanceEntry.objects.filter(
            student=self.request.user,
            is_valid=True
        ).select_related('session__course')
        return {'entries': entries}


class GamificationView(LoginRequiredMixin, StudentRequiredMixin, TemplateView):
    template_name = 'attendance/student/gamification.html'

    def get_context_data(self, **kwargs):
        user = self.request.user
        try:
            gamification, _ = GamificationPoints.objects.get_or_create(user=user)
        except:
            gamification, _ = GamificationPoints.objects.get_or_create(student=user)

        earned = StudentBadge.objects.filter(student=user).select_related('badge')
        earned_ids = [s.badge.id for s in earned]
        all_badges = Badge.objects.all().order_by('name')

        return {
            'gamification': gamification,
            'earned_student_badges': earned,
            'all_badges': all_badges,
            'earned_badge_ids': earned_ids,
        }


class UnreadNotificationCountView(View):
    def get(self, request):
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return JsonResponse({'count': count})


#shared profile view
class ProfileView(LoginRequiredMixin, TemplateView):
    def get_template_names(self):
        # This part remains correct for selecting the right template file
        if self.request.user.is_teacher or self.request.user.is_admin_role:
            return ['attendance/teacher/profile.html']
        return ['attendance/student/profile.html']

    def get_context_data(self, **kwargs):
        user = self.request.user
        # Fetching notifications is common to both roles
        notifications = Notification.objects.filter(user=user, is_read=False).order_by('-created_at')[:5]

        if user.is_teacher or user.is_admin_role:
            # TEACHER/ADMIN Context (Existing Logic)
            courses = Course.objects.filter(teacher=user)
            return {'courses': courses, 'notifications': notifications}

        # STUDENT Context (TWEAKED Logic)
        gamification, _ = GamificationPoints.objects.get_or_create(student=user)
        badges = StudentBadge.objects.filter(student=user)
        courses_enrolled = user.courses_enrolled.all() # <-- Added enrolled courses

        # Also fetch student_profile directly for easy access in the template
        student_profile = getattr(user, 'student_profile', None)

        return {
            'student_profile': student_profile, # <-- Added student_profile
            'courses_enrolled': courses_enrolled, # <-- Added enrolled courses
            'gamification': gamification, 
            'badges': badges, 
            'notifications': notifications
        }

# In attendance/views.py (NotificationsView)

from django.db.models import Case, When, BooleanField # NEW IMPORT

class NotificationsView(LoginRequiredMixin, TemplateView):
    template_name = 'attendance/notifications.html'

    def get_context_data(self, **kwargs):
        # 1. Order by unread first (False) then by creation date (descending)
        notifications = Notification.objects.filter(user=self.request.user).order_by(
            Case(
                When(is_read=False, then=0),
                default=1,
                output_field=BooleanField(),
            ),
            '-created_at'
        )
        
        return {'notifications': notifications}
    
    # We will DELETE the existing POST method since we will use a separate URL 
    # for the automatic mark-as-read action, or modify it to be more generic.
    # We'll stick to a simple endpoint for auto-read.
    def post(self, request):
        # Keep this for the auto-read endpoint, but simplify the logic
        notif_id = request.POST.get('notification_id')
        if notif_id:
            try:
                notif = Notification.objects.get(id=notif_id, user=request.user, is_read=False)
                notif.is_read = True
                notif.save()
                return JsonResponse({'success': True})
            except Notification.DoesNotExist:
                return JsonResponse({'success': False, 'message': 'Notification already read or not found'}, status=404)
        return JsonResponse({'success': False, 'message': 'Invalid ID'}, status=400)
    
class MarkNotificationReadView(LoginRequiredMixin, View):
    def post(self, request, notification_id):
        notif = get_object_or_404(Notification, id=notification_id, user=request.user)
        notif.is_read = True
        notif.save()
        return JsonResponse({'success': True})



class TeacherProfileUpdateView(TeacherRequiredMixin, UpdateView):
    """Allows the teacher to update their personal information and profile."""
    model = User
    # Use your custom User model and a form that includes fields from TeacherProfile
    # We will use the model.User fields for this example, assuming you manage the profile save in form_valid
    fields = ['first_name', 'last_name', 'email', 'phone', 'avatar'] # Use fields from User model
    template_name = 'attendance/teacher/profile_edit.html'
    
    def get_object(self):
        """Ensures only the current logged-in user can edit their profile."""
        return self.request.user
    
    def get_success_url(self):
        return reverse_lazy('profile')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Assuming you would use a separate formset/form to handle TeacherProfile fields
        # For simplicity, we'll keep the profile fields tied to the main User update here,
        # but a proper implementation would use nested forms or signal.
        return context


# --- Course Management Views ---

class CourseCreateView(TeacherRequiredMixin, CreateView):
    """Allows a teacher to create a new course."""
    model = Course
    # Note: students M2M field is usually managed separately after creation or via a custom form
    fields = ['name', 'code', 'description'] 
    template_name = 'attendance/teacher/course_form.html'
    success_url = reverse_lazy('teacher_dashboard')

    def form_valid(self, form):
        # Automatically set the teacher to the currently logged-in user
        form.instance.teacher = self.request.user
        messages.success(self.request, f"Course '{form.instance.name}' created successfully.")
        return super().form_valid(form)

class CourseUpdateView(TeacherRequiredMixin, UpdateView):
    """Allows a teacher to edit an existing course they own."""
    model = Course
    fields = ['name', 'code', 'description']
    template_name = 'attendance/teacher/course_form.html'

    def get_queryset(self):
        """Ensures the teacher can only edit their own courses."""
        return self.model.objects.filter(teacher=self.request.user)
    
    def get_success_url(self):
        messages.success(self.request, f"Course '{self.object.name}' updated successfully.")
        return reverse_lazy('teacher_dashboard')

class CourseDeleteView(TeacherRequiredMixin, DeleteView):
    """Allows a teacher to delete an existing course they own."""
    model = Course
    template_name = 'attendance/teacher/course_confirm_delete.html'
    success_url = reverse_lazy('teacher_dashboard')

    def get_queryset(self):
        """Ensures the teacher can only delete their own courses."""
        return self.model.objects.filter(teacher=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, f"Course '{self.object.name}' deleted successfully.")
        return super().form_valid(form)




class CourseDetailView(LoginRequiredMixin, DetailView):
    """
    Displays the details of a single course. 
    The logic in get_context_data will differentiate what data to show 
    based on the user's role (Teacher vs. Student).
    """
    model = Course
    context_object_name = 'course'
    pk_url_kwarg = 'course_id'  # Matches the argument name in the URL pattern

    def get_template_names(self):
        # Determine template based on role
        if self.request.user.is_teacher or self.request.user.is_admin_role:
            return ['attendance/teacher/course_detail.html']
        return ['attendance/student/course_detail.html'] # <-- Create this template later

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        course = context['course']
        
        if user.is_student:
            # Student-specific context: show their own attendance records
            context['attendance_records'] = AttendanceEntry.objects.filter(
                session__course=course, 
                student=user
            ).order_by('-timestamp')

        elif user.is_teacher or user.is_admin_role:
            # Teacher-specific context: show management links, session list, etc.
            context['sessions'] = course.sessions.all().order_by('-start_time')
            # Add more teacher-specific data as needed
            
        return context
    
   
# attendance/views.py

from django.shortcuts import render, redirect
from django.views.generic import TemplateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django import forms
from .models import User, StudentProfile, Notification, Course
# Import your specific forms if they exist, otherwise use ModelForm below

# --- Custom Forms for Student Profile Edit ---

class StudentUserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone', 'avatar']

class StudentProfileForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = ['department', 'year', 'section'] # student_id is usually not editable

# --- Student Views ---

class StudentRequiredMixin(UserPassesTestMixin):
    """Mixin to restrict access only to users with the 'student' role."""
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_student

class StudentProfileView(LoginRequiredMixin, StudentRequiredMixin, TemplateView):
    """Displays the student's profile, enrolled courses, and gamification points."""
    template_name = 'attendance/student/profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get student-specific data
        try:
            student_profile = user.student_profile
        except StudentProfile.DoesNotExist:
            student_profile = None

        context['student_profile'] = student_profile
        context['courses_enrolled'] = user.courses_enrolled.all()
        context['notifications'] = Notification.objects.filter(user=user, is_read=False).order_by('-created_at')[:5]
        
        # Gamification data (assuming you handle creation if it doesn't exist)
        context['gamification_points'] = getattr(user, 'gamification_points', None)
        
        return context


class StudentProfileEditView(LoginRequiredMixin, StudentRequiredMixin, UpdateView):
    """Allows students to edit their User and StudentProfile details."""
    model = User
    form_class = StudentUserForm
    template_name = 'attendance/student/profile_edit.html'
    success_url = reverse_lazy('student_profile')

    def get_object(self):
        # Ensure the user can only edit their own profile
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pass the associated StudentProfile form for inline editing
        if self.request.POST:
            context['profile_form'] = StudentProfileForm(self.request.POST, instance=self.request.user.student_profile)
        else:
            context['profile_form'] = StudentProfileForm(instance=self.request.user.student_profile)
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        profile_form = context['profile_form']

        if profile_form.is_valid():
            self.object = form.save()
            profile_form.save()
            messages.success(self.request, "Profile updated successfully.")
            return redirect(self.get_success_url())
        else:
            # If the profile form is invalid, re-render the page with errors
            return self.render_to_response(self.get_context_data(form=form))
        
        



class AddCourseView(LoginRequiredMixin, StudentRequiredMixin, View):
    """
    Handle adding a course to the student's profile via course code.
    """

    def post(self, request, *args, **kwargs):
        user = request.user
        course_code = request.POST.get('course_code', '').strip().upper()

        if not course_code:
            messages.error(request, "Please enter a course code.")
            return redirect('student_dashboard')

        try:
            # Optional: restrict courses to teacher's courses
            course = Course.objects.get(code=course_code)
            if course in user.courses_enrolled.all():
                messages.info(request, f"You are already enrolled in {course.name}.")
            else:
                user.courses_enrolled.add(course)
                messages.success(request, f"Successfully added course: {course.name}")
        except Course.DoesNotExist:
            messages.error(request, "Invalid course code. Please check and try again.")

        return redirect('profile')
    

# attendance/views.py

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.views import View
from django.db.models import Prefetch, Count, Q
from django.utils import timezone
from datetime import timedelta

# Assuming these models and mixins are imported from your project:
# from .models import Course, User, attendance_entries 
# from .mixins import LoginRequiredMixin, TeacherRequiredMixin 

# attendance/views.py

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.views import View
from django.db.models import Prefetch, Count, Q
from django.utils import timezone
from datetime import timedelta
# Assuming imports for LoginRequiredMixin, TeacherRequiredMixin, User, Course, etc.

class MyStudentsView(LoginRequiredMixin, TeacherRequiredMixin, View):
    """
    Handles both the full-page load (Master Roster) and AJAX fetch 
    (Course-specific Roster) for the teacher's students, including monthly stats.
    """
    template_name = 'attendance/teacher/my_students.html'
    partial_template_name = 'attendance/teacher/_student_list_table.html'

    def get(self, request: HttpRequest) -> HttpResponse:
        teacher = request.user
        course_id = request.GET.get('course_id') 

        # 1. Fetch teacher's courses efficiently
        courses_queryset = (
            Course.objects.filter(teacher=teacher)
            .annotate(student_count=Count('students'))
            .order_by('code')
        )

        selected_course = None
        students_data = [] 
        
        # --- Determine the scope of students and courses ---
        if not course_id or course_id == '0':
            # Master Roster: All students across all courses
            courses_to_fetch = courses_queryset
            
            courses_with_students = (
                courses_to_fetch
                .prefetch_related(
                    Prefetch(
                        'students', 
                        queryset=User.objects.filter(role='student')
                                             .select_related('student_profile', 'gamification_points')
                    )
                )
            )

            student_set = {}
            for course in courses_with_students:
                for student in course.students.all():
                    student_id = student.id
                    
                    if student_id not in student_set:
                        student_set[student_id] = {
                            'student': student,
                            'courses': [course],
                        }
                    else:
                        student_set[student_id]['courses'].append(course)

            students_data = list(student_set.values())
            # Sorting is done here for the master roster
            students_data.sort(key=lambda x: x['student'].last_name or '') 
            
            # Use all courses for attendance filtering in the master view
            attendance_courses = courses_queryset 

        else:
            # Course-Specific Roster: Students only in the selected course
            try:
                selected_course = get_object_or_404(courses_queryset, id=course_id)
                course_students = (
                    selected_course.students.filter(role='student')
                    .select_related('student_profile', 'gamification_points')
                    .order_by('last_name')
                )
                
                students_data = [{
                    'student': student, 
                    'courses': [selected_course]
                } for student in course_students]
                
                # Use only the selected course for attendance filtering
                attendance_courses = Course.objects.filter(pk=selected_course.pk)
                
            except (ValueError, TypeError):
                pass
        
        # --- ATTENDANCE STATS CALCULATION ---
        today = timezone.localdate()
        start_of_month = today.replace(day=1)
        
        # Get IDs of all students in the roster
        student_ids = [data['student'].id for data in students_data]
        
        # Get course IDs as a list for correct filtering in Q() objects
        attendance_course_ids = attendance_courses.values_list('id', flat=True)
        
        # Annotate the student QuerySet with monthly stats
        # The lookup is corrected to: attendance_entries -> session -> course -> id
        annotated_students_qs = User.objects.filter(id__in=student_ids).filter(role='student').annotate(
            # Count Present statuses for the current month and relevant courses
            month_presents=Count('attendance_entries', filter=
                Q(attendance_entries__session__course__id__in=attendance_course_ids, # <-- CORRECTED PATH
                  attendance_entries__timestamp__date__gte=start_of_month,            # <-- Filtering by date of timestamp
                  attendance_entries__is_valid=True)                                # <-- Assuming "Present" means 'is_valid=True'
            ),
            # Count Absences (Invalid or Missing Entries)
            # NOTE: True 'Absence' is usually lack of an AttendanceEntry. 
            # This counts INVALID entries (not present).
            month_invalid_entries=Count('attendance_entries', filter=
                Q(attendance_entries__session__course__id__in=attendance_course_ids, # <-- CORRECTED PATH
                  attendance_entries__timestamp__date__gte=start_of_month, 
                  attendance_entries__is_valid=False)                               # <-- Assuming "Absent/Invalid" means 'is_valid=False'
            ),
            # Count the total number of relevant sessions attended
            month_total_sessions=Count('attendance_entries', filter=
                Q(attendance_entries__session__course__id__in=attendance_course_ids, # <-- CORRECTED PATH
                  attendance_entries__timestamp__date__gte=start_of_month)
            ) 
        ).select_related('student_profile', 'gamification_points')
        
        # Map the annotated students back to the students_data structure
        annotated_student_map = {s.id: s for s in annotated_students_qs}

        for data in students_data:
            student = annotated_student_map.get(data['student'].id)
            if student:
                data['student'] = student
                
                # CALCULATE ATTENDANCE RATE IN PYTHON
                total = student.month_total_sessions
                presents = student.month_presents
                
                if total > 0:
                    rate = (presents / total) * 100
                    data['student'].attendance_rate = f"{rate:.0f}"
                else:
                    data['student'].attendance_rate = 'N/A'
                    
                # Re-map the 'absences' field for consistency with the template
                # Note: The 'month_absences' in the template context should correspond 
                # to the calculated month_invalid_entries here.
                data['student'].month_absences = student.month_invalid_entries


        context = {
            'courses': courses_queryset,
            'selected_course': selected_course,
            'students_data': students_data,
            'is_master_roster': not selected_course,
            'current_month': today.strftime('%B'),
        }
        
        # --- Handle Request Type ---
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'

        if is_ajax:
            return render(request, self.partial_template_name, context)
        
        return render(request, self.template_name, context)

from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth 
from django.utils import timezone
# Ensure you import your models and mixins here
# from .models import User, Course, AttendanceEntry 
# from .mixins import LoginRequiredMixin, TeacherRequiredMixin, ...



from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth

# Assuming these imports exist in your project setup
# from .mixins import TeacherRequiredMixin 
# from users.models import User
# from attendance.models import AttendanceEntry 
# from courses.models import Course 
# NOTE: Replace 'User' and 'AttendanceEntry' with your actual imported models.

class StudentDetailTeacherView(LoginRequiredMixin, TeacherRequiredMixin, TemplateView):
    """
    Displays the detailed profile and attendance analytics for a single student. 
    Data includes overall stats, monthly attendance trends for charting, and 
    a detailed session history, all filtered to courses the current teacher shares with the student.
    """
    template_name = 'attendance/teacher/student_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        teacher = self.request.user
        student_id = kwargs.get('student_id')

        # 1. Fetch teacher's courses and define authorization scope
        teacher_courses_qs = teacher.courses_taught.all()
        
        # 2. Authorize and fetch the student
        # Assuming User is imported and has 'role', 'courses_enrolled' relations
        student_queryset = (
            User.objects.filter(role='student')
            .filter(courses_enrolled__in=teacher_courses_qs)
            .distinct() 
            .select_related('student_profile', 'gamification_points')
        )
        student = get_object_or_404(student_queryset, id=student_id)
        
        # 3. Determine the set of courses shared between the student and teacher
        shared_courses_qs = teacher_courses_qs.filter(students=student).order_by('code')
        shared_course_ids = shared_courses_qs.values_list('id', flat=True)
        
        # 4. Context Course (for highlighting, if applicable)
        context_course = None
        course_id = kwargs.get('course_id')
        if course_id:
            # We fetch it again using shared_courses_qs to ensure teacher has access
            context_course = get_object_or_404(shared_courses_qs, id=course_id)
        
        # ----------------------------------------------------------------------
        # 5. OVERALL ATTENDANCE STATISTICS (Across all shared courses)
        # ----------------------------------------------------------------------
        # This part looks robust and doesn't need changes.
        student_with_stats = User.objects.filter(pk=student.pk).annotate(
            all_time_presents=Count('attendance_entries', filter=
                Q(attendance_entries__session__course__id__in=shared_course_ids, 
                  attendance_entries__is_valid=True)
            ),
            all_time_invalid=Count('attendance_entries', filter=
                Q(attendance_entries__session__course__id__in=shared_course_ids, 
                  attendance_entries__is_valid=False)
            ),
            all_time_total_entries=Count('attendance_entries', filter=
                Q(attendance_entries__session__course__id__in=shared_course_ids)
            )
        ).first()

        presents = student_with_stats.all_time_presents
        total_entries = student_with_stats.all_time_total_entries
        
        attendance_rate = 0
        if total_entries > 0:
            attendance_rate = (presents / total_entries) * 100

        attendance_stats = {
            'rate': f"{attendance_rate:.0f}",
            'presents': presents,
            'invalid': student_with_stats.all_time_invalid,
            'total': total_entries,
        }
        
        # ----------------------------------------------------------------------
        # 6. MONTHLY ATTENDANCE TRENDS (Chart Data)
        # ----------------------------------------------------------------------
        # This section is fine, as .values() and list() handle date serialization for json_script.
        monthly_stats_qs = (
            AttendanceEntry.objects.filter(
                student=student,
                session__course__id__in=shared_course_ids
            )
            .annotate(month=TruncMonth('session__start_time'))
            .values('month')
            .annotate(
                presents=Count('pk', filter=Q(is_valid=True)),
                invalid=Count('pk', filter=Q(is_valid=False)),
                total=Count('pk')
            )
            .order_by('month') 
        )
        monthly_stats = list(monthly_stats_qs)

        # CRITICAL FIX: Ensure 'month' datetime objects are converted to strings for JSON
        for stat in monthly_stats:
             if 'month' in stat and stat['month']:
                 stat['month'] = stat['month'].isoformat()
        
        # ----------------------------------------------------------------------
        # 7. DETAILED ATTENDANCE HISTORY (Grouped by Course) - NOW WITH SERIALIZATION
        # ----------------------------------------------------------------------
        attendance_history_qs = (
            AttendanceEntry.objects.filter(
                student=student,
                session__course__id__in=shared_course_ids
            )
            .select_related('session__course', 'session')
            .order_by('-session__start_time')
        )
        
        # Group history by course name and manually serialize relevant fields for JavaScript
        history_by_course = {}
        for entry in attendance_history_qs:
            course_name = f"{entry.session.course.code} - {entry.session.course.name}"
            
            # Use the session's start time as the general time reference if the 
            # AttendanceEntry itself doesn't have a check-in time field, 
            # or use 'created_at' if that exists. For robustness, using start_time.
            timestamp_to_use = entry.session.start_time 
            
            serialized_entry = {
                # This field is needed by the JS to parse the date
                'timestamp': timestamp_to_use.isoformat(), 
                'is_valid': entry.is_valid,
                'session': {
                    'name': entry.session.course.name,
                    'code' : entry.session.course.code,
                    # We only need the name for display, other data is redundant if the timestamp is present
                },
                'timestamp_display': entry.timestamp
            }
            
            if course_name not in history_by_course:
                history_by_course[course_name] = []
            
            history_by_course[course_name].append(serialized_entry)


        # 8. Final Context Update
        context.update({
            'student': student,
            'shared_courses': shared_courses_qs,
            'context_course': context_course,
            'attendance_stats': attendance_stats,
            'monthly_stats': monthly_stats, 
            'history_by_course': history_by_course, 
        })
        return context