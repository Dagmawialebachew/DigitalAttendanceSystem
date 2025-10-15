#!/bin/bash

echo "=================================="
echo "Digital Attendance System Setup"
echo "=================================="
echo ""

echo "Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi
echo "✓ Python 3 found"

echo ""
echo "Installing dependencies..."
pip3 install -r requirements.txt

echo ""
echo "Running migrations..."
python3 manage.py makemigrations
python3 manage.py migrate

echo ""
echo "Creating demo data..."
python3 setup.py

echo ""
echo "=================================="
echo "Setup Complete!"
echo "=================================="
echo ""
echo "To start the application:"
echo ""
echo "1. Start Redis (in a separate terminal):"
echo "   redis-server"
echo ""
echo "2. Start the Django server:"
echo "   python3 manage.py runserver"
echo ""
echo "3. Open your browser:"
echo "   http://localhost:8000"
echo ""
echo "=================================="
echo "Login Credentials:"
echo "=================================="
echo ""
echo "Teacher: teacher@example.com / password"
echo "Student: alice@example.com / password"
echo ""
echo "=================================="
