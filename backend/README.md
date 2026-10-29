# MentorConnect API

## Run locally

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # optional; defaults work for local SQLite
uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs

### Demo accounts
All demo passwords: `Mentor123!`

- Admin: `admin@mentorconnect.edu`
- Mentor: `mentor@mentorconnect.edu`
- Student: `student@mentorconnect.edu`
- Second student: `kabir@mentorconnect.edu`

The backend seeds fictional demo users and records on first run. SQLite is used by default; set `DATABASE_URL` for PostgreSQL. Change `SECRET_KEY` before deployment. This is a portfolio starter, not a security-audited production system.

Student accounts can be created by an administrator through `POST /api/v1/students`; provide `mentor_id` to establish the initial assignment. Mentors can update only students assigned to them through `PATCH /api/v1/students/{student_id}`. New accounts use a random password hash that is not returned; implement an invitation or password-reset flow before enabling sign-in for newly provisioned students.

Run the API tests with `pip install -r requirements-dev.txt` followed by `python -m unittest discover -s tests`.
