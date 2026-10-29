# MentorConnect

A full-stack student mentorship and academic progress management starter with three distinct role-based dashboards: Student, Mentor, and Administrator.

## Stack
- React + Vite + JavaScript, custom responsive CSS, Lucide React, Recharts
- FastAPI + SQLAlchemy + Pydantic
- SQLite by default; PostgreSQL supported through `DATABASE_URL`
- JWT authentication and Argon2 password hashing

## Run the backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env # optional for local SQLite
uvicorn app.main:app --reload
```
Backend API docs: http://localhost:8000/docs

## Run the frontend
Open a second terminal:
```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```
Open the Vite URL shown in the terminal, usually http://localhost:5173.

## Demo login
All demo accounts use password `Mentor123!`:
- Student: `student@mentorconnect.edu`
- Mentor: `mentor@mentorconnect.edu`
- Administrator: `admin@mentorconnect.edu`
- Second student: `kabir@mentorconnect.edu`

The backend creates fictional seed users, assignments, sample marks, notes, and recommendations on first startup.

## Student management
Sign in as an administrator and open **Students → Add student** to create a student account and assign it to an active mentor. Mentors can edit the profile details of students assigned to them; student account creation and mentor assignment remain administrator-only. Passwords are never returned by the API; new accounts receive a random password hash, so add an account invitation/password-reset workflow before using newly created accounts for student sign-in.

## Important notes
This is a portfolio-ready development starter, not a production security audit. Before deploying, set a strong `SECRET_KEY`, use PostgreSQL, enforce HTTPS, configure origins, add refresh-token rotation/revocation, rate limiting, account provisioning, backup policies, and a complete authorization review. Demo credentials are for local use only.
