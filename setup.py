#!/usr/bin/env python3
"""
Setup script for the Attendance System
This script initializes the database and creates demo data
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'attendance_system.settings')
django.setup()

from django.contrib.auth import get_user_model
from attendance.models import (
    TeacherProfile, StudentProfile, Course, Badge,
    GamificationPoints
)

User = get_user_model()


def create_demo_data():
    print("Creating demo data...")

    if User.objects.filter(email='admin@example.com').exists():
        print("Demo data already exists. Skipping...")
        return

    admin = User.objects.create_superuser(
        email='admin@example.com',
        password='password',
        first_name='Admin',
        last_name='User',
        role='admin'
    )
    print(f"✓ Created admin: {admin.email}")

    teacher = User.objects.create_user(
        email='teacher@example.com',
        password='password',
        first_name='John',
        last_name='Smith',
        role='teacher'
    )
    TeacherProfile.objects.create(
        user=teacher,
        employee_id='T001',
        department='Computer Science',
        subject='Programming',
        bio='Experienced programming instructor'
    )
    print(f"✓ Created teacher: {teacher.email}")

    students_data = [
        {'first': 'Alice', 'last': 'Johnson', 'id': 'S001'},
        {'first': 'Bob', 'last': 'Williams', 'id': 'S002'},
        {'first': 'Charlie', 'last': 'Brown', 'id': 'S003'},
        {'first': 'Diana', 'last': 'Davis', 'id': 'S004'},
        {'first': 'Eve', 'last': 'Miller', 'id': 'S005'},
    ]

    students = []
    for data in students_data:
        student = User.objects.create_user(
            email=f"{data['first'].lower()}@example.com",
            password='password',
            first_name=data['first'],
            last_name=data['last'],
            role='student'
        )
        StudentProfile.objects.create(
            user=student,
            student_id=data['id'],
            department='Computer Science',
            year=2,
            section='A'
        )
        GamificationPoints.objects.create(student=student, total_points=0)
        students.append(student)
        print(f"✓ Created student: {student.email}")

    course1 = Course.objects.create(
        name='Introduction to Programming',
        code='CS101',
        description='Learn the basics of programming with Python',
        teacher=teacher
    )
    course1.students.set(students)
    print(f"✓ Created course: {course1.code}")

    course2 = Course.objects.create(
        name='Web Development',
        code='CS201',
        description='Build modern web applications',
        teacher=teacher
    )
    course2.students.set(students[:3])
    print(f"✓ Created course: {course2.code}")

    badges_data = [
        {
            'name': 'First Timer',
            'description': 'Attended your first session',
            'badge_type': 'bronze',
            'icon': '🥉',
            'required_points': 10,
            'required_streak': 0
        },
        {
            'name': 'Regular',
            'description': 'Attended 10 sessions',
            'badge_type': 'silver',
            'icon': '🥈',
            'required_points': 100,
            'required_streak': 0
        },
        {
            'name': 'Dedicated',
            'description': 'Attended 50 sessions',
            'badge_type': 'gold',
            'icon': '🥇',
            'required_points': 500,
            'required_streak': 0
        },
        {
            'name': 'Streak Master',
            'description': '7 day attendance streak',
            'badge_type': 'gold',
            'icon': '🔥',
            'required_points': 0,
            'required_streak': 7
        },
        {
            'name': 'Perfect Month',
            'description': '30 day attendance streak',
            'badge_type': 'platinum',
            'icon': '💎',
            'required_points': 0,
            'required_streak': 30
        },
    ]

    for badge_data in badges_data:
        Badge.objects.create(**badge_data)
    print(f"✓ Created {len(badges_data)} badges")

    print("\n" + "="*60)
    print("Demo data created successfully!")
    print("="*60)
    print("\nLogin credentials:")
    print("\nAdmin:")
    print("  Email: admin@example.com")
    print("  Password: password")
    print("\nTeacher:")
    print("  Email: teacher@example.com")
    print("  Password: password")
    print("\nStudents:")
    print("  Email: alice@example.com (or bob, charlie, diana, eve)")
    print("  Password: password")
    print("="*60)


if __name__ == '__main__':
    create_demo_data()
