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
        if AttendanceEntry.objects.filter(session=session, student=student).exists():
            InvalidAttempt.objects.create(
                session=session,
                student=student,
                code_submitted=code,
                ip_address=ip_address,
                device_info=device_info,
                reason='Duplicate submission'
            )
            return False, 'Already submitted for this session'

        if not session.is_valid():
            InvalidAttempt.objects.create(
                session=session,
                student=student,
                code_submitted=code,
                ip_address=ip_address,
                device_info=device_info,
                reason='Session expired'
            )
            return False, 'Session has expired'

        is_valid = code == session.code

        entry = AttendanceEntry.objects.create(
            session=session,
            student=student,
            code_submitted=code,
            is_valid=is_valid,
            ip_address=ip_address,
            device_info=device_info
        )

        if is_valid:
            GamificationService.award_points(student, 10)
            NotificationService.notify_attendance_marked(student, session)
            AttendanceService.broadcast_update(session)
            return True, 'Attendance marked successfully'
        else:
            InvalidAttempt.objects.create(
                session=session,
                student=student,
                code_submitted=code,
                ip_address=ip_address,
                device_info=device_info,
                reason='Invalid code'
            )
            return False, 'Invalid code'

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
    def broadcast_update(session):
        channel_layer = get_channel_layer()
        entries = AttendanceEntry.objects.filter(session=session, is_valid=True)

        data = {
            'session_id': session.id,
            'total_present': entries.count(),
            'entries': [
                {
                    'student_name': entry.student.get_full_name(),
                    'student_email': entry.student.email,
                    'timestamp': entry.timestamp.isoformat(),
                    'manually_added': entry.manually_added
                }
                for entry in entries
            ]
        }

        async_to_sync(channel_layer.group_send)(
            f'attendance_{session.id}',
            {
                'type': 'attendance_update',
                'data': data
            }
        )

    @staticmethod
    def end_session(session):
        session.end_session()
        AttendanceService.broadcast_session_ended(session)
        EmailService.send_attendance_recap(session)

    @staticmethod
    def broadcast_session_ended(session):
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'attendance_{session.id}',
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


class NotificationService:
    @staticmethod
    def create_notification(user, notification_type, title, message, link=''):
        notification = Notification.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
            link=link
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
                    'link': link,
                    'created_at': notification.created_at.isoformat()
                }
            }
        )

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
