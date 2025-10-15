import re
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

import csv
from .models import (
    User, Course, AttendanceSession, AttendanceEntry,
    GamificationPoints, Badge, StudentBadge, Notification
)
from .services import AttendanceService, GamificationService


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
        ugr = request.POST.get('ugr')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        teacher_id = request.POST.get('teacher_id')  # optional validation only

        # Validate UGR format
        if not re.match(r'^UGR/\d{4}/\d{2}$', ugr):
            messages.error(request, "Invalid UGR format. Example: UGR/8286/17")
            return render(request, self.template_name, {'ugr': ugr, 'teacher_id': teacher_id})

        # Check password match
        if password != confirm_password:
            messages.error(request, "Passwords do not match")
            return render(request, self.template_name, {'ugr': ugr, 'teacher_id': teacher_id})

        # Optional: validate teacher exists
        if teacher_id and not User.objects.filter(teacher_profile__employee_id=teacher_id, role='teacher').exists():
            messages.error(request, "Teacher ID not found")
            return render(request, self.template_name, {'ugr': ugr, 'teacher_id': teacher_id})

        # Check if user already exists
        email = f"{ugr}@school.com"
        user, created = User.objects.get_or_create(email=email, defaults={'role': 'student'})

        if created:
            user.set_password(password)
            user.save()
            messages.success(request, "Account created successfully. You can now login.")
        else:
            messages.info(request, "Account already exists. You can login.")

        # Ensure StudentProfile exists
        StudentProfile.objects.get_or_create(user=user, defaults={'student_id': ugr})

        return redirect('login')


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


class AnalyticsView(LoginRequiredMixin, TeacherRequiredMixin, TemplateView):
    template_name = 'attendance/teacher/analytics.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        courses = Course.objects.filter(teacher=self.request.user)
        course_id = self.request.GET.get('course')
        context['courses'] = courses

        if course_id:
            selected_course = get_object_or_404(Course, id=course_id, teacher=self.request.user)
            sessions = AttendanceSession.objects.filter(course=selected_course, status='ended')
            data = []
            for s in sessions:
                present = AttendanceEntry.objects.filter(session=s, is_valid=True).count()
                total = selected_course.students.count()
                data.append({
                    'date': s.start_time.strftime('%Y-%m-%d'),
                    'present': present,
                    'total': total,
                    'percentage': (present / total * 100) if total > 0 else 0
                })
            context['selected_course'] = selected_course
            context['attendance_data'] = data
        else:
            context['selected_course'] = None
            context['attendance_data'] = []
        return context


class ExportAttendanceView(LoginRequiredMixin, TeacherRequiredMixin, View):
    def get(self, request, session_id):
        session = get_object_or_404(AttendanceSession, id=session_id, teacher=request.user)
        entries = AttendanceEntry.objects.filter(session=session, is_valid=True).select_related('student')

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="attendance_{session.code}.csv"'
        writer = csv.writer(response)
        writer.writerow(['Student Name', 'Email', 'Student ID', 'Timestamp', 'Manually Added'])

        for e in entries:
            writer.writerow([
                e.student.get_full_name(),
                e.student.email,
                getattr(e.student.student_profile, 'student_id', ''),
                e.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'Yes' if e.manually_added else 'No'
            ])
        return response


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
        session = get_object_or_404(AttendanceSession, id=session_id, status='active')
        return render(request, self.template_name, {'session': session, 'is_valid': session.is_valid()})

    def post(self, request, session_id):
        session = get_object_or_404(AttendanceSession, id=session_id, status='active')
        if request.user not in session.course.students.all():
            messages.error(request, 'You are not enrolled in this course')
            return redirect('student_dashboard')

        code = request.POST.get('code', '').upper()
        ip = request.META.get('REMOTE_ADDR')
        device = request.META.get('HTTP_USER_AGENT', '')
        success, msg = AttendanceService.submit_attendance(session, request.user, code, ip, device)

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

class NotificationsView(LoginRequiredMixin, TemplateView):
    template_name = 'attendance/notifications.html'

    def get_context_data(self, **kwargs):
        return {'notifications': Notification.objects.filter(user=self.request.user)}

    def post(self, request):
        notif_id = request.POST.get('notification_id')
        notif = get_object_or_404(Notification, id=notif_id, user=request.user)
        notif.is_read = True
        notif.save()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        return redirect('notifications')


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