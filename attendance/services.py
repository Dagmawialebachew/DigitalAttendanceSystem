from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import (
    AttendanceSession, AttendanceEntry, InvalidAttempt,
    GamificationPoints, Badge, StudentBadge, Notification
)


from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import AttendanceEntry


class AttendanceService:

    @staticmethod
    def create_session(course, teacher, duration_seconds=10):
        code = AttendanceSession.generate_code()
        while AttendanceSession.objects.filter(code=code, status='active').exists():
            code = AttendanceSession.generate_code()

        session = AttendanceSession.objects.create(
            course=course,
            teacher=teacher,
            code=code,
            duration_seconds=duration_seconds
        )

        NotificationService.notify_session_started(session)
        return session

    @staticmethod
    def submit_attendance(session, student, code, ip_address, device_info):
        if not session.is_valid():
            InvalidAttempt.objects.create(
                session=session,
                student=student,
                code_submitted=code,
                ip_address=ip_address,
                device_info=device_info,
                reason='Session expired'
            )
            return False, 'Session has expired', None

        if AttendanceEntry.objects.filter(session=session, student=student, is_valid=True).exists():
            return False, 'You have already submitted attendance', None

        is_valid = code == session.code

        if is_valid:
            entry = AttendanceEntry.objects.create(
                session=session,
                student=student,
                code_submitted=code,
                is_valid=True,
                ip_address=ip_address,
                device_info=device_info
            )
            # optional: notify / gamify
            NotificationService.notify_attendance_marked(student, session)
            AttendanceService.broadcast_update(session)
            return True, 'Attendance marked successfully', entry
        else:
            InvalidAttempt.objects.create(
                session=session,
                student=student,
                code_submitted=code,
                ip_address=ip_address,
                device_info=device_info,
                reason='Invalid code'
            )
            return False, 'Invalid code', None

    @staticmethod
    def broadcast_update(session):
        channel_layer = get_channel_layer()
        entries = AttendanceEntry.objects.filter(session=session, is_valid=True).order_by('-timestamp')
        if not entries.exists():
            return

        entry = entries.first()

        data = {
            'entry': {
                'id': entry.id,
                'student_name': entry.student.get_full_name(),
                'student_email': getattr(entry.student, 'email', 'No Email'),
                'timestamp': entry.timestamp.isoformat(),
                'student_id': getattr(getattr(entry.student, 'student_profile', None), 'student_id', 'N/A'),
                'manually_added': entry.manually_added
            },
            'total_present': entries.count()
        }

        async_to_sync(channel_layer.group_send)(
            f'attendance_session_{session.id}',
            {
                'type': 'attendance_update',
                'data': data
            }
        )

    @staticmethod
    def manual_override(session, student, added_by):
        entry, created = AttendanceEntry.objects.get_or_create(
            session=session,
            student=student,
            defaults={
                'code_submitted': session.code,
                'is_valid': True,
                'manually_added': True,
                'added_by': added_by
            }
        )

        if not created:
            entry.is_valid = True
            entry.manually_added = True
            entry.added_by = added_by
            entry.save()

        AttendanceService.broadcast_update(session)
        return entry
    
    @staticmethod
    def end_session(session):
        session.end_session()
        AttendanceService.broadcast_session_ended(session)
        EmailService.send_attendance_recap(session)
        TeacherNotificationService.notify_session_summary(session.teacher, session)
            # After summary
        recent_sessions = AttendanceSession.objects.filter(
            course=session.course,
            teacher=session.teacher
        ).exclude(id=session.id).order_by('-start_time')[:5]

        if recent_sessions.exists():
            total_rate = 0
            count = 0
            for s in recent_sessions:
                students = s.course.students.all()
                total_students = students.count()
                marked = s.entries.filter(is_valid=True).count()
                if total_students > 0:
                    total_rate += (marked / total_students * 100)
                    count += 1

            avg_rate = (total_rate / count) if count > 0 else 0
            TeacherNotificationService.notify_unusual_attendance(session.teacher, session, avg_rate)
            
        
                    # Inside end_session() after summary + unusual detection
            students = session.course.students.all()
            for student in students:
                # Count last 3 sessions (including current)
                recent_sessions = AttendanceSession.objects.filter(
                    course=session.course,
                    teacher=session.teacher
                ).order_by('-start_time')[:3]

                consecutive_misses = 0
                for s in recent_sessions:
                    marked = AttendanceEntry.objects.filter(session=s, student=student, is_valid=True).exists()
                    if not marked:
                        consecutive_misses += 1
                    else:
                        break  # break streak if present

                TeacherNotificationService.notify_absence_pattern(session.teacher, student, consecutive_misses)





    @staticmethod
    def broadcast_session_ended(session):
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'attendance_session_{session.id}',
            {
                'type': 'session_ended',
                'data': {'session_id': session.id}
            }
        )
        
        
class GamificationService:
    @staticmethod
    def award_points(student, points):
        gamification, created = GamificationPoints.objects.get_or_create(student=student)
        gamification.add_points(points)

        GamificationService.check_badges(student, gamification)

    @staticmethod
    def check_badges(student, gamification):
        eligible_badges = Badge.objects.filter(
            required_points__lte=gamification.total_points,
            required_streak__lte=gamification.streak_days
        )

        for badge in eligible_badges:
            if not StudentBadge.objects.filter(student=student, badge=badge).exists():
                StudentBadge.objects.create(student=student, badge=badge)
                NotificationService.notify_badge_earned(student, badge)
                TeacherNotificationService.notify_student_milestone(student.course.teacher, student, badge)


class NotificationService:
    @staticmethod
    def create_notification(user, notification_type, title, message, link='', 
                            course=None, session_date=None): # 🚨 NEW ARGUMENTS
        
        notification = Notification.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
            link=link,
            relevant_course=course,            # 🚨 NEW FIELD ASSIGNMENT
            relevant_date=session_date         # 🚨 NEW FIELD ASSIGNMENT
        )

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'notifications_{user.id}',
            {
                'type': 'notification',
                'data': {
                    'id': notification.id,
                    'type': notification_type,
                    'title': title,
                    'message': message,
                    # We don't send course/date over WebSocket yet, as the frontend uses AJAX to fetch the list anyway
                    'link': link, 
                    'created_at': notification.created_at.isoformat()
                }
            }
        )

    # Student-side notifications (mostly unchanged, no need for complex course/date tracking yet)
    @staticmethod
    def notify_session_started(session):
        for student in session.course.students.all():
            NotificationService.create_notification(
                user=student,
                notification_type='session_started',
                title='Attendance Session Started',
                message=f'Attendance session for {session.course.name} has started!',
                link=f'/student/submit/{session.id}/'
            )

    @staticmethod
    def notify_attendance_marked(student, session):
        # We can optionally add course/date here too, but for student link is enough
        NotificationService.create_notification(
            user=student,
            notification_type='attendance_marked',
            title='Attendance Marked',
            message=f'Your attendance for {session.course.name} has been marked successfully.',
            link='/student/history/'
        )

    @staticmethod
    def notify_badge_earned(student, badge):
        NotificationService.create_notification(
            user=student,
            notification_type='badge_earned',
            title='Badge Earned!',
            message=f'Congratulations! You earned the {badge.name} badge!',
            link='/student/gamification/'
        )
        
class TeacherNotificationService(NotificationService):

    @staticmethod
    def notify_session_summary(teacher, session):
        students = session.course.students.all()
        total_students = students.count()
        marked = session.entries.filter(is_valid=True).count()
        absent = total_students - marked

        attendance_rate = (marked / total_students * 100) if total_students > 0 else 0
        
        # Get the session date from the start_time field
        session_date = session.start_time.date() 

        NotificationService.create_notification(
            user=teacher,
            notification_type='session_summary',
            title=f'Attendance Summary: {session.course.name}',
            message=f'{marked} present, {absent} absent ({attendance_rate:.1f}% attendance) for today’s session.',
            link=f'/teacher/session/{session.id}/summary/',
            course=session.course,       # 🚨 ADDED
            session_date=session_date    # 🚨 ADDED
        )

    @staticmethod
    def notify_unusual_attendance(teacher, session, avg_attendance_rate):
        students = session.course.students.all()
        total_students = students.count()
        marked = session.entries.filter(is_valid=True).count()
        today_rate = (marked / total_students * 100) if total_students > 0 else 0
        session_date = session.start_time.date() # Get the session date

        # detect unusual dip (e.g. more than 15% lower than average)
        if today_rate < (avg_attendance_rate - 15):
            NotificationService.create_notification(
                user=teacher,
                notification_type='unusual_attendance',
                title='Unusual Attendance Detected',
                message=f"Today's attendance for {session.course.name} is {today_rate:.1f}%, "
                        f"below your usual {avg_attendance_rate:.1f}%.",
                link=f'/teacher/session/{session.id}/',
                course=session.course,       # 🚨 ADDED
                session_date=session_date    # 🚨 ADDED
            )

    @staticmethod
    def notify_student_milestone(teacher, student, milestone):
        # We don't have a course/session context here, so we skip the new fields.
        NotificationService.create_notification(
            user=teacher,
            notification_type='student_milestone',
            title='Student Milestone Reached',
            message=f'{student.full_name} has achieved the milestone: "{milestone.name}".',
            link=f'/teacher/students/{student.id}/'
        )

    @staticmethod
    def notify_absence_pattern(teacher, student, consecutive_misses):
        # We don't have a specific course/session context here, so we skip the new fields.
        if consecutive_misses >= 3:
            NotificationService.create_notification(
                user=teacher,
                notification_type='absence_pattern',
                title='Repeated Absences Detected',
                message=f'{student.full_name} has missed {consecutive_misses} consecutive sessions.',
                link=f'/teacher/students/{student.id}/attendance/'
            )
class EmailService:
    @staticmethod
    def send_attendance_recap(session):
        entries = AttendanceEntry.objects.filter(session=session, is_valid=True)
        present_students = [entry.student for entry in entries]
        all_students = session.course.students.all()
        absent_students = [s for s in all_students if s not in present_students]

        context = {
            'session': session,
            'course': session.course,
            'present_count': len(present_students),
            'absent_count': len(absent_students),
            'total_count': all_students.count(),
            'present_students': present_students,
            'absent_students': absent_students,
        }

        subject = f'Attendance Recap: {session.course.name} - {session.start_time.strftime("%Y-%m-%d")}'
        html_message = render_to_string('attendance/email/recap.html', context)
        plain_message = render_to_string('attendance/email/recap.txt', context)

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[session.teacher.email],
            html_message=html_message,
            fail_silently=True,
        )
