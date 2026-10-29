from datetime import datetime, timedelta, timezone
import logging
import os
import re
import secrets
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import create_engine, String, Integer, Float, Boolean, DateTime, ForeignKey, Text, Index, func, inspect, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker, Session

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./mentorconnect.db")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-this-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = 90
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

class Base(DeclarativeBase): pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), index=True)
    department: Mapped[str] = mapped_column(String(100), default="Computer Science")
    student_code: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    semester: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

Index("uq_users_email_ci", func.lower(User.email), unique=True)
Index("uq_users_student_code_ci", func.upper(User.student_code), unique=True)

class Assignment(Base):
    __tablename__ = "assignments"
    id: Mapped[int] = mapped_column(primary_key=True)
    mentor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class AcademicRecord(Base):
    __tablename__ = "academic_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    semester: Mapped[int] = mapped_column(Integer)
    academic_year: Mapped[str] = mapped_column(String(20), default="2026-27")
    subject: Mapped[str] = mapped_column(String(120))
    subject_code: Mapped[str] = mapped_column(String(30), default="")
    max_marks: Mapped[float] = mapped_column(Float)
    obtained_marks: Mapped[float] = mapped_column(Float)
    grade: Mapped[str] = mapped_column(String(5), default="—")
    remarks: Mapped[str] = mapped_column(Text, default="")
    updated_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class MentoringNote(Base):
    __tablename__ = "mentoring_notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    mentor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    topic: Mapped[str] = mapped_column(String(180))
    content: Mapped[str] = mapped_column(Text)
    action_items: Mapped[str] = mapped_column(Text, default="")
    visible_to_student: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Recommendation(Base):
    __tablename__ = "recommendations"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    mentor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(50), default="Academic")
    priority: Mapped[str] = mapped_column(String(20), default="Medium")
    deadline: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", index=True)
    review_comment: Mapped[str] = mapped_column(Text, default="")
    reviewed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class LoginInput(BaseModel):
    email: str
    password: str
class RecordInput(BaseModel):
    semester: int = Field(ge=1, le=12)
    academic_year: str = "2026-27"
    subject: str = Field(min_length=1, max_length=120)
    subject_code: str = ""
    max_marks: float = Field(gt=0)
    obtained_marks: float = Field(ge=0)
    grade: str = "—"
    remarks: str = ""
class NoteInput(BaseModel):
    topic: str = Field(min_length=1, max_length=180)
    content: str = Field(min_length=1)
    action_items: str = ""
    visible_to_student: bool = False
class RecommendationInput(BaseModel):
    student_id: int
    title: str = Field(min_length=1, max_length=180)
    description: str = Field(min_length=1)
    category: str = "Academic"
    priority: str = "Medium"
    deadline: Optional[str] = None
class ReviewInput(BaseModel):
    decision: str
    comment: str = ""

class StudentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    student_code: str = Field(min_length=1, max_length=40)
    email: str = Field(min_length=3, max_length=180)
    department: str = Field(min_length=1, max_length=100)
    semester: int = Field(strict=True, ge=1, le=12)
    phone: Optional[str] = Field(default=None, max_length=40)
    mentor_id: int = Field(gt=0)

    @field_validator("name", "student_code", "department")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank")
        return value

    @field_validator("student_code")
    @classmethod
    def normalize_student_code(cls, value: str) -> str:
        return value.upper()

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Enter a valid email address")
        return value

    @field_validator("semester", mode="before")
    @classmethod
    def reject_boolean_semester(cls, value: int) -> int:
        if isinstance(value, bool):
            raise ValueError("Semester must be a whole number from 1 to 12")
        return value

    @field_validator("phone", mode="before")
    @classmethod
    def normalize_phone(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("Phone number must be text")
        value = value.strip()
        return value or None

class StudentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    email: Optional[str] = Field(default=None, min_length=3, max_length=180)
    department: Optional[str] = Field(default=None, min_length=1, max_length=100)
    semester: Optional[int] = Field(default=None, strict=True, ge=1, le=12)
    phone: Optional[str] = Field(default=None, max_length=40)

    @field_validator("name", "department")
    @classmethod
    def normalize_required_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank")
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Enter a valid email address")
        return value

    @field_validator("semester", mode="before")
    @classmethod
    def reject_boolean_semester(cls, value: Optional[int]) -> Optional[int]:
        if isinstance(value, bool):
            raise ValueError("Semester must be a whole number from 1 to 12")
        return value

    @field_validator("phone", mode="before")
    @classmethod
    def normalize_phone(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("Phone number must be text")
        value = value.strip()
        return value or None

app = FastAPI(title="MentorConnect API", version="1.0.0", description="Mentorship and academic progress API")
logger = logging.getLogger(__name__)
origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
app.add_middleware(CORSMiddleware, allow_origins=[origin, "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

def hash_password(password: str) -> str: return pwd_context.hash(password)
def verify_password(password: str, hashed: str) -> bool: return pwd_context.verify(password, hashed)
def create_token(user: User):
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(user.id), "role": user.role, "iat": now, "exp": now + timedelta(minutes=ACCESS_TOKEN_MINUTES)}, SECRET_KEY, algorithm=ALGORITHM)
def current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try: payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM]); uid = int(payload["sub"])
    except (JWTError, KeyError, ValueError): raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.get(User, uid)
    if not user or not user.active: raise HTTPException(status_code=401, detail="Account unavailable")
    return user
def require_role(*roles):
    def checker(user: User = Depends(current_user)):
        if user.role not in roles: raise HTTPException(status_code=403, detail="You do not have permission for this action")
        return user
    return checker
def audit(db, actor, action, entity_type, entity_id=None, details=""):
    db.add(AuditLog(actor_id=actor.id, action=action, entity_type=entity_type, entity_id=entity_id, details=details))
def assigned(db: Session, mentor_id: int, student_id: int) -> bool:
    return db.query(Assignment).filter_by(mentor_id=mentor_id, student_id=student_id, active=True).first() is not None
def can_access_student(db: Session, user: User, student_id: int) -> bool:
    if user.role == "ADMIN": return True
    if user.role == "STUDENT": return user.id == student_id
    return user.role == "MENTOR" and assigned(db, user.id, student_id)
def user_out(u: User): return {"id":u.id,"name":u.name,"email":u.email,"role":u.role,"department":u.department,"student_code":u.student_code,"semester":u.semester,"phone":u.phone,"active":u.active}
def record_out(r: AcademicRecord): return {"id":r.id,"student_id":r.student_id,"semester":r.semester,"academic_year":r.academic_year,"subject":r.subject,"subject_code":r.subject_code,"max_marks":r.max_marks,"obtained_marks":r.obtained_marks,"percentage":round(r.obtained_marks/r.max_marks*100,1),"grade":r.grade,"remarks":r.remarks,"updated_at":r.updated_at.isoformat()}
def note_out(n: MentoringNote, db: Session): return {"id":n.id,"student_id":n.student_id,"mentor_id":n.mentor_id,"mentor_name":db.get(User,n.mentor_id).name,"topic":n.topic,"content":n.content,"action_items":n.action_items,"visible_to_student":n.visible_to_student,"created_at":n.created_at.isoformat()}
def rec_out(r: Recommendation, db: Session): return {"id":r.id,"student_id":r.student_id,"student_name":db.get(User,r.student_id).name,"mentor_id":r.mentor_id,"mentor_name":db.get(User,r.mentor_id).name,"title":r.title,"description":r.description,"category":r.category,"priority":r.priority,"deadline":r.deadline,"status":r.status,"review_comment":r.review_comment,"created_at":r.created_at.isoformat()}

def migrate_schema():
    Base.metadata.create_all(bind=engine)
    user_columns = {column["name"] for column in inspect(engine).get_columns("users")}
    with engine.begin() as connection:
        if "semester" not in user_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN semester INTEGER"))
        if "phone" not in user_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN phone VARCHAR(40)"))
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_ci ON users (lower(email))"))
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_student_code_ci ON users (upper(student_code))"))

def seed():
    migrate_schema()
    db = SessionLocal()
    try:
        if db.query(User).count(): return
        admin=User(name="Aarav Menon",email="admin@mentorconnect.edu",password_hash=hash_password("Mentor123!"),role="ADMIN",department="Administration")
        mentor=User(name="Dr. Meera Rao",email="mentor@mentorconnect.edu",password_hash=hash_password("Mentor123!"),role="MENTOR",department="Artificial Intelligence")
        s1=User(name="Riya Sharma",email="student@mentorconnect.edu",password_hash=hash_password("Mentor123!"),role="STUDENT",department="Artificial Intelligence",student_code="MC2026001")
        s2=User(name="Kabir Nair",email="kabir@mentorconnect.edu",password_hash=hash_password("Mentor123!"),role="STUDENT",department="Computer Science",student_code="MC2026002")
        db.add_all([admin,mentor,s1,s2]); db.flush()
        db.add_all([Assignment(mentor_id=mentor.id,student_id=s1.id),Assignment(mentor_id=mentor.id,student_id=s2.id)])
        db.add_all([
          AcademicRecord(student_id=s1.id,semester=5,academic_year="2025-26",subject="Machine Learning",subject_code="AIM501",max_marks=100,obtained_marks=88,grade="A",remarks="Strong conceptual understanding",updated_by=mentor.id),
          AcademicRecord(student_id=s1.id,semester=5,academic_year="2025-26",subject="Database Systems",subject_code="CS502",max_marks=100,obtained_marks=79,grade="B+",remarks="Practice query optimization",updated_by=mentor.id),
          AcademicRecord(student_id=s1.id,semester=5,academic_year="2025-26",subject="Computer Networks",subject_code="CS503",max_marks=100,obtained_marks=84,grade="A",remarks="Good progress",updated_by=mentor.id),
          AcademicRecord(student_id=s2.id,semester=5,academic_year="2025-26",subject="Machine Learning",subject_code="AIM501",max_marks=100,obtained_marks=74,grade="B",remarks="Revise evaluation metrics",updated_by=mentor.id),
          MentoringNote(student_id=s1.id,mentor_id=mentor.id,topic="Mid-semester check-in",content="Riya is progressing well. Focus on SQL practice before the next review.",action_items="Complete 10 SQL problems this week",visible_to_student=True),
          Recommendation(student_id=s1.id,mentor_id=mentor.id,title="Strengthen SQL problem solving",description="Practice joins, window functions, and query optimization for technical interviews.",category="Career Preparation",priority="High",deadline="2026-11-15",status="PENDING_REVIEW"),
          Recommendation(student_id=s2.id,mentor_id=mentor.id,title="Review ML evaluation metrics",description="Revise precision, recall, F1-score, and confusion matrices.",category="Academic",priority="Medium",status="ENDORSED",review_comment="Good actionable recommendation.",reviewed_by=admin.id)
        ])
        db.commit()
    finally: db.close()

@app.on_event("startup")
def startup(): seed()

@app.get("/api/v1/health")
def health(): return {"status":"ok","service":"MentorConnect API"}

@app.post("/api/v1/auth/login")
def login(data: LoginInput, db: Session = Depends(get_db)):
    user=db.query(User).filter(User.email==data.email.lower()).first()
    if not user or not verify_password(data.password,user.password_hash): raise HTTPException(status_code=401,detail="Invalid email or password")
    return {"access_token":create_token(user),"token_type":"bearer","user":user_out(user)}

@app.get("/api/v1/auth/me")
def me(user: User = Depends(current_user)): return user_out(user)

@app.get("/api/v1/users")
def list_users(role: Optional[str]=None, db: Session=Depends(get_db), user: User=Depends(require_role("ADMIN"))):
    q=db.query(User)
    if role: q=q.filter(User.role==role.upper())
    return [user_out(u) for u in q.order_by(User.name).all()]

@app.post("/api/v1/assignments")
def create_assignment(data: dict, db: Session=Depends(get_db), user: User=Depends(require_role("ADMIN"))):
    mentor=db.get(User,int(data.get("mentor_id",0))); student=db.get(User,int(data.get("student_id",0)))
    if not mentor or mentor.role!="MENTOR" or not student or student.role!="STUDENT": raise HTTPException(422,"A valid mentor and student are required")
    existing=db.query(Assignment).filter_by(mentor_id=mentor.id,student_id=student.id).first()
    if existing: existing.active=True; item=existing
    else: item=Assignment(mentor_id=mentor.id,student_id=student.id); db.add(item)
    audit(db,user,"ASSIGN_MENTOR","Assignment",None,f"mentor={mentor.id};student={student.id}"); db.commit(); db.refresh(item)
    return {"id":item.id,"mentor_id":item.mentor_id,"student_id":item.student_id,"active":item.active}

@app.get("/api/v1/assignments")
def list_assignments(db: Session=Depends(get_db), user: User=Depends(current_user)):
    q=db.query(Assignment).filter(Assignment.active==True)
    if user.role=="MENTOR": q=q.filter(Assignment.mentor_id==user.id)
    elif user.role=="STUDENT": q=q.filter(Assignment.student_id==user.id)
    return [{"id":a.id,"mentor":user_out(db.get(User,a.mentor_id)),"student":user_out(db.get(User,a.student_id)),"active":a.active} for a in q.all()]

@app.get("/api/v1/students")
def students(db: Session=Depends(get_db), user: User=Depends(current_user)):
    q=db.query(User).filter(User.role=="STUDENT")
    if user.role=="STUDENT": q=q.filter(User.id==user.id)
    elif user.role=="MENTOR": q=q.join(Assignment,Assignment.student_id==User.id).filter(Assignment.mentor_id==user.id,Assignment.active==True)
    elif user.role!="ADMIN": raise HTTPException(403,"Forbidden")
    return [user_out(s) for s in q.order_by(User.name).all()]

@app.get("/api/v1/students/{student_id}")
def student_detail(student_id:int, db:Session=Depends(get_db), user:User=Depends(current_user)):
    if not can_access_student(db,user,student_id): raise HTTPException(403,"You cannot access this student")
    s=db.get(User,student_id)
    if not s or s.role!="STUDENT": raise HTTPException(404,"Student not found")
    return user_out(s)

@app.post("/api/v1/students", status_code=201)
def create_student(data: StudentCreate, db: Session=Depends(get_db), user: User=Depends(require_role("ADMIN"))):
    try:
        mentor = db.get(User, data.mentor_id)
        if not mentor or mentor.role != "MENTOR" or not mentor.active:
            raise HTTPException(status_code=422, detail="Select an active mentor")
        if db.query(User).filter(func.lower(User.email) == data.email).first():
            raise HTTPException(status_code=409, detail="A user with this email address already exists")
        if db.query(User).filter(func.upper(User.student_code) == data.student_code).first():
            raise HTTPException(status_code=409, detail="A student with this student ID already exists")

        student = User(
            name=data.name,
            email=data.email,
            password_hash=hash_password(secrets.token_urlsafe(32)),
            role="STUDENT",
            department=data.department,
            student_code=data.student_code,
            semester=data.semester,
            phone=data.phone,
        )
        db.add(student)
        db.flush()
        assignment = db.query(Assignment).filter_by(mentor_id=mentor.id, student_id=student.id).first()
        if assignment:
            assignment.active = True
        else:
            db.add(Assignment(mentor_id=mentor.id, student_id=student.id, active=True))
        audit(db, user, "CREATE_STUDENT", "User", student.id)
        db.commit()
        db.refresh(student)
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A user with this email address or student ID already exists")
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Could not create student")
        raise HTTPException(status_code=500, detail="Could not save the student. Please try again.")
    return user_out(student)

@app.patch("/api/v1/students/{student_id}")
def update_student(student_id: int, data: StudentUpdate, db: Session=Depends(get_db), user: User=Depends(require_role("ADMIN", "MENTOR"))):
    try:
        if not can_access_student(db, user, student_id):
            raise HTTPException(status_code=403, detail="You are not assigned to this student")
        student = db.get(User, student_id)
        if not student or student.role != "STUDENT":
            raise HTTPException(status_code=404, detail="Student not found")

        changes = data.model_dump(exclude_unset=True)
        if not changes:
            raise HTTPException(status_code=422, detail="Provide at least one student field to update")
        if any(changes.get(field) is None for field in ("name", "email", "department", "semester") if field in changes):
            raise HTTPException(status_code=422, detail="Name, email, department, and semester cannot be empty")
        if "email" in changes and db.query(User).filter(
            func.lower(User.email) == changes["email"], User.id != student_id
        ).first():
            raise HTTPException(status_code=409, detail="A user with this email address already exists")

        for field, value in changes.items():
            setattr(student, field, value)
        audit(db, user, "UPDATE_STUDENT", "User", student.id)
        db.commit()
        db.refresh(student)
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A user with this email address already exists")
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Could not update student %s", student_id)
        raise HTTPException(status_code=500, detail="Could not save student changes. Please try again.")
    return user_out(student)

@app.get("/api/v1/students/{student_id}/academic-records")
def get_records(student_id:int, db:Session=Depends(get_db), user:User=Depends(current_user)):
    if not can_access_student(db,user,student_id): raise HTTPException(403,"You cannot access these records")
    return [record_out(r) for r in db.query(AcademicRecord).filter_by(student_id=student_id).order_by(AcademicRecord.semester.desc()).all()]

@app.post("/api/v1/students/{student_id}/academic-records")
def add_record(student_id:int,data:RecordInput,db:Session=Depends(get_db),user:User=Depends(require_role("MENTOR","ADMIN"))):
    if not can_access_student(db,user,student_id): raise HTTPException(403,"You are not assigned to this student")
    if data.obtained_marks>data.max_marks: raise HTTPException(422,"Obtained marks cannot exceed maximum marks")
    r=AcademicRecord(student_id=student_id,updated_by=user.id,**data.model_dump()); db.add(r); db.flush(); audit(db,user,"CREATE_ACADEMIC_RECORD","AcademicRecord",r.id,f"student={student_id}"); db.commit(); db.refresh(r); return record_out(r)

@app.get("/api/v1/students/{student_id}/mentoring-notes")
def get_notes(student_id:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
    if not can_access_student(db,user,student_id): raise HTTPException(403,"You cannot access these notes")
    q=db.query(MentoringNote).filter_by(student_id=student_id)
    if user.role=="STUDENT": q=q.filter(MentoringNote.visible_to_student==True)
    return [note_out(n,db) for n in q.order_by(MentoringNote.created_at.desc()).all()]

@app.post("/api/v1/students/{student_id}/mentoring-notes")
def add_note(student_id:int,data:NoteInput,db:Session=Depends(get_db),user:User=Depends(require_role("MENTOR","ADMIN"))):
    if not can_access_student(db,user,student_id): raise HTTPException(403,"You are not assigned to this student")
    n=MentoringNote(student_id=student_id,mentor_id=user.id,**data.model_dump()); db.add(n); db.flush(); audit(db,user,"CREATE_MENTORING_NOTE","MentoringNote",n.id); db.commit(); db.refresh(n); return note_out(n,db)

@app.get("/api/v1/recommendations")
def get_recommendations(db:Session=Depends(get_db),user:User=Depends(current_user)):
    q=db.query(Recommendation)
    if user.role=="STUDENT": q=q.filter(Recommendation.student_id==user.id)
    elif user.role=="MENTOR": q=q.filter(Recommendation.mentor_id==user.id)
    return [rec_out(r,db) for r in q.order_by(Recommendation.created_at.desc()).all()]

@app.post("/api/v1/recommendations")
def create_recommendation(data:RecommendationInput,db:Session=Depends(get_db),user:User=Depends(require_role("MENTOR"))):
    if not assigned(db,user.id,data.student_id): raise HTTPException(403,"You can only recommend for assigned students")
    r=Recommendation(mentor_id=user.id,**data.model_dump()); db.add(r); db.flush(); audit(db,user,"CREATE_RECOMMENDATION","Recommendation",r.id); db.commit(); db.refresh(r); return rec_out(r,db)

@app.post("/api/v1/recommendations/{recommendation_id}/submit")
def submit_recommendation(recommendation_id:int,db:Session=Depends(get_db),user:User=Depends(require_role("MENTOR"))):
    r=db.get(Recommendation,recommendation_id)
    if not r: raise HTTPException(404,"Recommendation not found")
    if r.mentor_id!=user.id: raise HTTPException(403,"Not your recommendation")
    if r.status not in ("DRAFT","REVISION_REQUESTED"): raise HTTPException(409,"Recommendation cannot be submitted from its current state")
    r.status="PENDING_REVIEW"; audit(db,user,"SUBMIT_RECOMMENDATION","Recommendation",r.id); db.commit(); db.refresh(r); return rec_out(r,db)

@app.post("/api/v1/recommendations/{recommendation_id}/review")
def review_recommendation(recommendation_id:int,data:ReviewInput,db:Session=Depends(get_db),user:User=Depends(require_role("ADMIN"))):
    r=db.get(Recommendation,recommendation_id)
    if not r: raise HTTPException(404,"Recommendation not found")
    decision=data.decision.upper()
    if r.status!="PENDING_REVIEW": raise HTTPException(409,"Only pending recommendations can be reviewed")
    if decision not in ("ENDORSED","REJECTED","REVISION_REQUESTED"): raise HTTPException(422,"Invalid review decision")
    if decision in ("REJECTED","REVISION_REQUESTED") and not data.comment.strip(): raise HTTPException(422,"A comment is required for this decision")
    r.status=decision; r.review_comment=data.comment; r.reviewed_by=user.id
    audit(db,user,decision,"Recommendation",r.id,data.comment); db.commit(); db.refresh(r); return rec_out(r,db)

@app.get("/api/v1/dashboard/{role}")
def dashboard(role:str,db:Session=Depends(get_db),user:User=Depends(current_user)):
    if role.lower()!=user.role.lower(): raise HTTPException(403,"You cannot access another role's dashboard")
    if user.role=="STUDENT":
        records=db.query(AcademicRecord).filter_by(student_id=user.id).all(); recs=db.query(Recommendation).filter_by(student_id=user.id).all()
        avg=round(sum(r.obtained_marks/r.max_marks*100 for r in records)/len(records),1) if records else None
        return {"role":"STUDENT","academic_average":avg,"record_count":len(records),"recommendations_count":len(recs),"pending_actions":sum(1 for r in recs if r.status in ("ENDORSED","REVISION_REQUESTED")),"recent_records":[record_out(r) for r in records[-5:]]}
    if user.role=="MENTOR":
        student_ids=[a.student_id for a in db.query(Assignment).filter_by(mentor_id=user.id,active=True).all()]
        recs=db.query(Recommendation).filter_by(mentor_id=user.id).all()
        return {"role":"MENTOR","assigned_students":len(student_ids),"pending_reviews":sum(1 for r in recs if r.status=="PENDING_REVIEW"),"recommendations":len(recs),"students":[user_out(db.get(User,sid)) for sid in student_ids]}
    return {"role":"ADMIN","students":db.query(User).filter_by(role="STUDENT").count(),"mentors":db.query(User).filter_by(role="MENTOR").count(),"assignments":db.query(Assignment).filter_by(active=True).count(),"pending_reviews":db.query(Recommendation).filter_by(status="PENDING_REVIEW").count(),"endorsed":db.query(Recommendation).filter_by(status="ENDORSED").count(),"recommendations":db.query(Recommendation).count()}

@app.get("/api/v1/audit-logs")
def get_audit_logs(db:Session=Depends(get_db),user:User=Depends(require_role("ADMIN"))):
    rows=db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(200).all()
    return [{"id":a.id,"actor":db.get(User,a.actor_id).name,"action":a.action,"entity_type":a.entity_type,"entity_id":a.entity_id,"details":a.details,"created_at":a.created_at.isoformat()} for a in rows]
