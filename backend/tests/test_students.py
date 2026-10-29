import os
import unittest

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "test-only-secret"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import (
    Assignment,
    Base,
    User,
    app,
    create_token,
    get_db,
)


class StudentEndpointTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False)
        Base.metadata.create_all(bind=self.engine)

        with self.session_factory() as db:
            self.admin = User(
                name="Admin User",
                email="admin@example.edu",
                password_hash="admin-hash",
                role="ADMIN",
                department="Administration",
            )
            self.mentor = User(
                name="Mentor One",
                email="mentor@example.edu",
                password_hash="mentor-hash",
                role="MENTOR",
                department="Computer Science",
            )
            self.other_mentor = User(
                name="Mentor Two",
                email="mentor2@example.edu",
                password_hash="mentor-hash",
                role="MENTOR",
                department="Mathematics",
            )
            self.assigned_student = User(
                name="Assigned Student",
                email="assigned@example.edu",
                password_hash="existing-student-hash",
                role="STUDENT",
                department="Computer Science",
                student_code="STU-001",
                semester=3,
                phone="5550100",
            )
            self.unassigned_student = User(
                name="Unassigned Student",
                email="unassigned@example.edu",
                password_hash="existing-student-hash",
                role="STUDENT",
                department="Mathematics",
                student_code="STU-002",
                semester=2,
            )
            db.add_all([self.admin, self.mentor, self.other_mentor, self.assigned_student, self.unassigned_student])
            db.flush()
            db.add(Assignment(mentor_id=self.mentor.id, student_id=self.assigned_student.id, active=True))
            db.commit()
            self.admin_id = self.admin.id
            self.mentor_id = self.mentor.id
            self.other_mentor_id = self.other_mentor.id
            self.assigned_student_id = self.assigned_student.id
            self.unassigned_student_id = self.unassigned_student.id
            self.original_password_hash = self.assigned_student.password_hash

        def override_get_db():
            with self.session_factory() as db:
                yield db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.admin_headers = {"Authorization": f"Bearer {create_token(self.admin)}"}
        self.mentor_headers = {"Authorization": f"Bearer {create_token(self.mentor)}"}
        self.other_mentor_headers = {"Authorization": f"Bearer {create_token(self.other_mentor)}"}

    def tearDown(self):
        app.dependency_overrides.pop(get_db, None)
        self.engine.dispose()

    def student_payload(self, **overrides):
        payload = {
            "name": "New Student",
            "student_code": "stu-003",
            "email": "NEW.Student@example.edu",
            "department": "Computer Science",
            "semester": 4,
            "phone": "555-0123",
            "mentor_id": self.mentor_id,
        }
        payload.update(overrides)
        return payload

    def test_admin_can_create_student_and_assignment(self):
        response = self.client.post(
            "/api/v1/students",
            json=self.student_payload(),
            headers=self.admin_headers,
        )

        self.assertEqual(response.status_code, 201)
        result = response.json()
        self.assertEqual(result["role"], "STUDENT")
        self.assertEqual(result["student_code"], "STU-003")
        self.assertEqual(result["email"], "new.student@example.edu")
        self.assertEqual(result["semester"], 4)
        self.assertEqual(result["phone"], "555-0123")
        self.assertNotIn("password_hash", result)

        with self.session_factory() as db:
            saved = db.get(User, result["id"])
            self.assertNotEqual(saved.password_hash, "")
            self.assertTrue(
                db.query(Assignment).filter_by(
                    mentor_id=self.mentor_id,
                    student_id=result["id"],
                    active=True,
                ).first()
            )
        listed = self.client.get("/api/v1/students", headers=self.admin_headers)
        self.assertIn(result["id"], {student["id"] for student in listed.json()})

    def test_create_requires_admin_authentication(self):
        self.assertEqual(self.client.post("/api/v1/students", json=self.student_payload()).status_code, 401)
        response = self.client.post(
            "/api/v1/students",
            json=self.student_payload(),
            headers=self.mentor_headers,
        )
        self.assertEqual(response.status_code, 403)

    def test_cors_allows_default_and_fallback_vite_origins(self):
        for origin in ("http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174"):
            with self.subTest(origin=origin):
                response = self.client.options(
                    "/api/v1/auth/login",
                    headers={
                        "Origin": origin,
                        "Access-Control-Request-Method": "POST",
                        "Access-Control-Request-Headers": "content-type",
                    },
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers.get("access-control-allow-origin"), origin)

    def test_create_rejects_missing_invalid_and_bad_email_fields(self):
        missing = self.student_payload()
        del missing["semester"]
        self.assertEqual(self.client.post("/api/v1/students", json=missing, headers=self.admin_headers).status_code, 422)

        invalid_semester = self.client.post(
            "/api/v1/students",
            json=self.student_payload(semester=13),
            headers=self.admin_headers,
        )
        self.assertEqual(invalid_semester.status_code, 422)
        boolean_semester = self.client.post(
            "/api/v1/students",
            json=self.student_payload(semester=True),
            headers=self.admin_headers,
        )
        self.assertEqual(boolean_semester.status_code, 422)

        invalid_email = self.client.post(
            "/api/v1/students",
            json=self.student_payload(email="not-an-email"),
            headers=self.admin_headers,
        )
        self.assertEqual(invalid_email.status_code, 422)

    def test_create_rejects_duplicate_student_ids_and_emails(self):
        duplicate_id = self.client.post(
            "/api/v1/students",
            json=self.student_payload(student_code="stu-001"),
            headers=self.admin_headers,
        )
        self.assertEqual(duplicate_id.status_code, 409)
        self.assertIn("student ID", duplicate_id.json()["detail"])

        duplicate_email = self.client.post(
            "/api/v1/students",
            json=self.student_payload(email="ASSIGNED@example.edu"),
            headers=self.admin_headers,
        )
        self.assertEqual(duplicate_email.status_code, 409)
        self.assertIn("email address", duplicate_email.json()["detail"])

    def test_mentor_can_update_assigned_student_without_changing_credentials(self):
        forbidden_fields = self.client.patch(
            f"/api/v1/students/{self.assigned_student_id}",
            json={"role": "ADMIN", "password_hash": "attacker-controlled"},
            headers=self.mentor_headers,
        )
        self.assertEqual(forbidden_fields.status_code, 422)

        response = self.client.patch(
            f"/api/v1/students/{self.assigned_student_id}",
            json={
                "name": "Updated Student",
                "email": "UPDATED@example.edu",
                "department": "Data Science",
                "semester": 5,
                "phone": "555-9999",
            },
            headers=self.mentor_headers,
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["name"], "Updated Student")
        self.assertEqual(result["email"], "updated@example.edu")
        self.assertEqual(result["department"], "Data Science")
        self.assertEqual(result["semester"], 5)
        self.assertEqual(result["phone"], "555-9999")
        self.assertEqual(result["role"], "STUDENT")
        with self.session_factory() as db:
            saved = db.get(User, self.assigned_student_id)
            self.assertEqual(saved.password_hash, self.original_password_hash)

    def test_update_rejects_duplicate_email_and_invalid_values(self):
        duplicate = self.client.patch(
            f"/api/v1/students/{self.assigned_student_id}",
            json={"email": "unassigned@example.edu"},
            headers=self.mentor_headers,
        )
        self.assertEqual(duplicate.status_code, 409)

        invalid = self.client.patch(
            f"/api/v1/students/{self.assigned_student_id}",
            json={"semester": 0},
            headers=self.mentor_headers,
        )
        self.assertEqual(invalid.status_code, 422)

        empty = self.client.patch(
            f"/api/v1/students/{self.assigned_student_id}",
            json={},
            headers=self.mentor_headers,
        )
        self.assertEqual(empty.status_code, 422)

    def test_update_requires_authentication_and_assigned_mentor(self):
        self.assertEqual(
            self.client.patch(
                f"/api/v1/students/{self.assigned_student_id}",
                json={"name": "No token"},
            ).status_code,
            401,
        )
        unassigned = self.client.patch(
            f"/api/v1/students/{self.unassigned_student_id}",
            json={"name": "Unauthorized edit"},
            headers=self.mentor_headers,
        )
        self.assertEqual(unassigned.status_code, 403)

        other_mentor = self.client.patch(
            f"/api/v1/students/{self.assigned_student_id}",
            json={"name": "Unauthorized edit"},
            headers=self.other_mentor_headers,
        )
        self.assertEqual(other_mentor.status_code, 403)

    def test_database_errors_roll_back_student_creation(self):
        def fail_commit(_session):
            raise SQLAlchemyError("injected commit failure")

        event.listen(self.session_factory.class_, "before_commit", fail_commit)
        try:
            response = self.client.post(
                "/api/v1/students",
                json=self.student_payload(),
                headers=self.admin_headers,
            )
        finally:
            event.remove(self.session_factory.class_, "before_commit", fail_commit)

        self.assertEqual(response.status_code, 500)
        with self.session_factory() as db:
            self.assertIsNone(db.query(User).filter_by(student_code="STU-003").first())


if __name__ == "__main__":
    unittest.main()
