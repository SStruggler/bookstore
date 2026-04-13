from fastapi import FastAPI, Depends, HTTPException, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from pydantic import BaseModel
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

# ==============================
# DATABASE CONFIG
# ==============================
DATABASE_URL = "mysql+pymysql://root:%5SGUTS.suriya5%@localhost/bookstore"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# ==============================
# MODEL
# ==============================
class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    age = Column(Integer)
    department = Column(String(100))
    marks = Column(Float)

# ==============================
# SCHEMA
# ==============================
class StudentCreate(BaseModel):
    name: str
    age: int
    department: str
    marks: float

class StudentResponse(StudentCreate):
    id: int

    class Config:
        from_attributes = True

class ChatRequest(BaseModel):
    message: str


def answer_from_student_data(message: str, students: list[Student]) -> str:
    if not students:
        return "No student records are available right now."

    msg = message.lower()
    if "top" in msg or "highest" in msg or "best" in msg:
        top = max(students, key=lambda s: s.marks)
        return f"Top student is {top.name} from {top.department} with {top.marks} marks."

    if "average" in msg or "mean" in msg:
        avg = sum(s.marks for s in students) / len(students)
        return f"The average marks are {avg:.2f} across {len(students)} students."

    if "how many" in msg or "count" in msg or "number" in msg:
        if "department" in msg:
            counts = {}
            for s in students:
                counts[s.department] = counts.get(s.department, 0) + 1
            parts = [f"{dept}: {count}" for dept, count in counts.items()]
            return "Student count by department is " + ", ".join(parts) + "."
        return f"There are {len(students)} students in the database."

    if "list" in msg or "names" in msg or "who" in msg:
        names = ", ".join(s.name for s in students[:10])
        return f"Students include: {names}."

    if "marks" in msg and "department" in msg:
        dept = None
        for s in students:
            if s.department.lower() in msg:
                dept = s.department
                break
        if dept:
            dept_students = [s for s in students if s.department == dept]
            if dept_students:
                names = ", ".join(s.name for s in dept_students)
                return f"Students in {dept}: {names}."

    return "I can answer questions about student names, departments, marks, and counts based on the current data."


# ==============================
# APP
# ==============================
app = FastAPI()

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

# ==============================
# DB DEPENDENCY
# ==============================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==============================
# UI ROUTES
# ==============================
@app.get("/")
def home(request: Request, db: Session = Depends(get_db), edit_id: int | None = None):
    students = db.query(Student).all()
    edit_student = None
    if edit_id:
        edit_student = db.query(Student).filter(Student.id == edit_id).first()

    return templates.TemplateResponse(request, "index.html", {
        "request": request,
        "students": students,
        "edit_student": edit_student
    })

@app.get("/edit/{student_id}")
def edit_page(request: Request, student_id: int, db: Session = Depends(get_db)):
    students = db.query(Student).all()
    edit_student = db.query(Student).filter(Student.id == student_id).first()

    return templates.TemplateResponse(request, "index.html", {
        "request": request,
        "students": students,
        "edit_student": edit_student
    })

# ==============================
# FORM CRUD
# ==============================
@app.post("/students/form")
def create_student_form(
    name: str = Form(...),
    age: int = Form(...),
    department: str = Form(...),
    marks: float = Form(...),
    db: Session = Depends(get_db),
):
    student = Student(name=name, age=age, department=department, marks=marks)
    db.add(student)
    db.commit()
    return RedirectResponse("/", status_code=303)

@app.post("/students/edit/{student_id}")
def update_student_form(
    student_id: int,
    name: str = Form(...),
    age: int = Form(...),
    department: str = Form(...),
    marks: float = Form(...),
    db: Session = Depends(get_db),
):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(404, "Not found")

    student.name = name
    student.age = age
    student.department = department
    student.marks = marks
    db.commit()

    return RedirectResponse("/", status_code=303)

@app.get("/delete/{student_id}")
def delete_student(student_id: int, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()
    if student:
        db.delete(student)
        db.commit()
    return RedirectResponse("/", status_code=303)

@app.get("/students", response_model=list[StudentResponse])
def get_students(db: Session = Depends(get_db)):
    students = db.query(Student).all()
    return students

# ==============================
# MINI AI CHATBOT
# ==============================
@app.post("/chat-mini")
def chat_mini(request: ChatRequest, db: Session = Depends(get_db)):
    
    students = db.query(Student).all()

    local_response = answer_from_student_data(request.message, students)
    return {"response": local_response}
