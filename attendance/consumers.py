import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import AttendanceSession

class AttendanceConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.user = self.scope['user']
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.room_group_name = f'attendance_session_{self.session_id}'

        # Join session group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

        # Send existing attendance entries
        entries = await self.get_attendance_entries()
        await self.send(text_data=json.dumps({
            "type": "attendance_entries",
            "entries": entries
        }))

        # Optionally send active sessions if needed
        sessions_data = await self.get_active_sessions_data()
        await self.send(text_data=json.dumps({
            "type": "active_sessions",
            "sessions": sessions_data
        }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')

        if message_type == 'ping':
            await self.send(text_data=json.dumps({
                'type': 'pong',
                'timestamp': timezone.now().isoformat()
            }))

    # Handler for attendance update broadcast
    async def attendance_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'attendance_update',
            'data': event['data']
        }))

    # Handler for session ended
    async def session_ended(self, event):
        await self.send(text_data=json.dumps({
            'type': 'session_ended',
            'data': event['data']
        }))

    @database_sync_to_async
    def get_attendance_entries(self):
        try:
            session = AttendanceSession.objects.get(id=self.session_id)
            entries = session.entries.select_related('student').all()
            return [
                {
                    "id": e.id,
                    "student_name": e.student.get_full_name(),
                    "student_email": getattr(e.student, 'email', 'No Email'),
                    "student_id": getattr(getattr(e.student, 'student_profile', None), 'student_id', 'N/A'),
                    "timestamp": e.timestamp.isoformat(),
                    "student_id": getattr(getattr(e.student, 'student_profile', None), 'student_id', 'N/A'),

                    "manually_added": e.manually_added
                } for e in entries
            ]
        except AttendanceSession.DoesNotExist:
            return []

    @database_sync_to_async
    def get_active_sessions_data(self):
        active_sessions = AttendanceSession.get_active_sessions()
        sessions_data = []

        for s in active_sessions:
            sessions_data.append({
                "id": s.id,
                "course": getattr(s.course, 'name', 'Unknown'),
                "code": s.code,
                "start_time": s.start_time.isoformat(),
                "end_time": s.end_time.isoformat() if s.end_time else None,
                "recommended_duration_seconds": 15
            })
        return sessions_data

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user_id = self.scope['user'].id
        self.room_group_name = f'notifications_{self.user_id}'

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def notification(self, event):
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'data': event['data']
        }))
