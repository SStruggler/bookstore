from fastapi import FastAPI, Depends, HTTPException, Form, Request
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from pydantic import BaseModel
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

# ==============================
# DATABASE CONFIG
# ==============================
DATABASE_URL = "mysql+pymysql://root:%5SGUTS.suriya%@localhost/bookstore"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()

# ==============================
# MODEL
# ==============================
class Bookstore(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    book_name = Column(String(100))
    author = Column(String(50))
    catagory = Column(String(100))
    price = Column(Float)
    stock = Column(Integer)

# Create table
Base.metadata.create_all(bind=engine)

# ==============================
# SCHEMA
# ==============================
class BookCreate(BaseModel):
    book_name: str
    author: str
    catagory: str
    price: float
    stock: int

class BookResponse(BookCreate):
    id: int

    class Config:
        from_attributes = True

# ==============================
# CHATBOT SCHEMA
# ==============================
class ChatMessage(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str

def answer_from_book_data(message: str, books: list[Bookstore]) -> str:
    if not books:
        return "No book records are available right now."

    msg = message.lower()
    if "top" in msg or "highest" in msg or "best" in msg or "expensive" in msg:
        if "price" in msg:
            top = max(books, key=lambda b: b.price)
            return f"The most expensive book is '{top.book_name}' by {top.author} in {top.catagory} category, priced at ${top.price:.2f}."
        elif "stock" in msg:
            top = max(books, key=lambda b: b.stock)
            return f"The book with the highest stock is '{top.book_name}' by {top.author}, with {top.stock} copies."

    if "average" in msg or "mean" in msg:
        if "price" in msg:
            avg = sum(b.price for b in books) / len(books)
            return f"The average price of books is ${avg:.2f} across {len(books)} books."
        elif "stock" in msg:
            avg = sum(b.stock for b in books) / len(books)
            return f"The average stock is {avg:.1f} across {len(books)} books."

    if "how many" in msg or "count" in msg or "number" in msg:
        if "category" in msg or "catagory" in msg:
            counts = {}
            for b in books:
                counts[b.catagory] = counts.get(b.catagory, 0) + 1
            parts = [f"{cat}: {count}" for cat, count in counts.items()]
            return "Book count by category: " + ", ".join(parts) + "."
        return f"There are {len(books)} books in the database."

    if "list" in msg or "names" in msg or "books" in msg:
        names = ", ".join(f"'{b.book_name}' by {b.author}" for b in books[:10])
        return f"Books include: {names}."

    if "author" in msg:
        authors = set(b.author for b in books)
        return f"Authors: {', '.join(authors)}."

    if "category" in msg or "catagory" in msg:
        categories = set(b.catagory for b in books)
        return f"Categories: {', '.join(categories)}."

    return "I can answer questions about book names, authors, categories, prices, and stock based on the current data."

def find_mistakes(books: list[Bookstore]) -> list[str]:
    mistakes = []
    for b in books:
        if b.price < 0:
            mistakes.append(f"Book '{b.book_name}' has negative price: ${b.price}")
        if b.stock < 0:
            mistakes.append(f"Book '{b.book_name}' has negative stock: {b.stock}")
        if not b.book_name.strip():
            mistakes.append(f"Book id {b.id} has empty name")
        if not b.author.strip():
            mistakes.append(f"Book '{b.book_name}' has empty author")
        if not b.catagory.strip():
            mistakes.append(f"Book '{b.book_name}' has empty category")
    return mistakes

def correct_mistakes(db: Session, books: list[Bookstore]) -> str:
    corrected = 0
    for b in books:
        changed = False
        if b.price < 0:
            b.price = 0
            changed = True
        if b.stock < 0:
            b.stock = 0
            changed = True
        if not b.book_name.strip():
            b.book_name = "Unknown"
            changed = True
        if not b.author.strip():
            b.author = "Unknown"
            changed = True
        if not b.catagory.strip():
            b.catagory = "Unknown"
            changed = True
        if changed:
            corrected += 1
    if corrected:
        db.commit()
        return f"Corrected mistakes in {corrected} books."
    return "No mistakes to correct."

# ==============================
# FASTAPI APP
# ==============================
app = FastAPI()

# ==============================
# DB DEPENDENCY
# ==============================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
templates = Jinja2Templates(directory="templates")

app.mount("/static", StaticFiles(directory="static"), name="static")

# ==============================
# CHATBOT ENDPOINTS
# ==============================
@app.post("/chat")
def chat(request: ChatMessage, db: Session = Depends(get_db)):
    books = db.query(Bookstore).all()
    msg = request.message.strip()

    # Handle commands
    if msg.lower().startswith("add book:"):
        try:
            parts = msg[9:].split(",")
            if len(parts) != 5:
                return ChatResponse(response="Invalid format. Use: add book: name, author, category, price, stock")
            name, author, cat, price_str, stock_str = [p.strip() for p in parts]
            price = float(price_str)
            stock = int(stock_str)
            new_book = Bookstore(book_name=name, author=author, catagory=cat, price=price, stock=stock)
            db.add(new_book)
            db.commit()
            return ChatResponse(response=f"Added book '{name}' successfully.")
        except ValueError:
            return ChatResponse(response="Invalid price or stock. Use numbers.")
        except Exception as e:
            return ChatResponse(response=f"Error adding book: {str(e)}")

    elif msg.lower().startswith("update book:"):
        try:
            parts = msg[12:].split(",")
            if len(parts) != 2:
                return ChatResponse(response="Invalid format. Use: update book: id, field=value")
            id_str, update_str = [p.strip() for p in parts]
            book_id = int(id_str)
            field, value = update_str.split("=")
            field = field.strip().lower()
            value = value.strip()
            book = db.query(Bookstore).filter(Bookstore.id == book_id).first()
            if not book:
                return ChatResponse(response="Book not found.")
            if field == "name":
                book.book_name = value
            elif field == "author":
                book.author = value
            elif field == "category":
                book.catagory = value
            elif field == "price":
                book.price = float(value)
            elif field == "stock":
                book.stock = int(value)
            else:
                return ChatResponse(response="Invalid field. Use name, author, category, price, or stock.")
            db.commit()
            return ChatResponse(response=f"Updated book {book_id} successfully.")
        except ValueError:
            return ChatResponse(response="Invalid id, price, or stock.")
        except Exception as e:
            return ChatResponse(response=f"Error updating book: {str(e)}")

    elif msg.lower().startswith("delete book:"):
        try:
            book_id = int(msg[12:].strip())
            book = db.query(Bookstore).filter(Bookstore.id == book_id).first()
            if not book:
                return ChatResponse(response="Book not found.")
            db.delete(book)
            db.commit()
            return ChatResponse(response=f"Deleted book {book_id} successfully.")
        except ValueError:
            return ChatResponse(response="Invalid id.")
        except Exception as e:
            return ChatResponse(response=f"Error deleting book: {str(e)}")

    elif "find mistakes" in msg.lower():
        mistakes = find_mistakes(books)
        if mistakes:
            return ChatResponse(response="Mistakes found:\n" + "\n".join(mistakes))
        else:
            return ChatResponse(response="No mistakes found.")

    elif "correct mistakes" in msg.lower():
        response = correct_mistakes(db, books)
        return ChatResponse(response=response)

    # Otherwise, answer questions
    response = answer_from_book_data(request.message, books)
    return ChatResponse(response=response)

# ==============================
# CRUD APIs
# ==============================
@app.get("/")
def home(request: Request, db: Session = Depends(get_db), edit_id: int | None = None):
    students = db.query(Bookstore).all()
    edit_student = None
    if edit_id is not None:
        edit_student = db.query(Bookstore).filter(Bookstore.id == edit_id).first()
    return templates.TemplateResponse(request, "index.html", {
        "request": request,
        "students": students,
        "edit_student": edit_student,
    })

@app.get("/edit/{student_id}")
def edit_student_page(request: Request, student_id: int, db: Session = Depends(get_db)):
    students = db.query(Bookstore).all()
    edit_student = db.query(Bookstore).filter(Bookstore.id == student_id).first()
    return templates.TemplateResponse(request, "index.html", {
        "request": request,
        "students": students,
        "edit_student": edit_student,
    })

@app.post("/students/form")
def create_student_form(
    request: Request,
    book_name: str = Form(...),
    author: str = Form(...),
    catagory: str = Form(...),
    price: float = Form(...),
    stock: int = Form(...),
    db: Session = Depends(get_db),
):
    new_book = Bookstore(book_name=book_name, author=author, catagory=catagory, price=price, stock=stock)
    db.add(new_book)
    db.commit()
    db.refresh(new_book)
    return RedirectResponse(url="/", status_code=303)

@app.post("/students/edit/{student_id}")
def update_student_form(
    student_id: int,
    book_name: str = Form(...),
    author: str = Form(...),
    catagory: str = Form(...),
    price: float = Form(...),
    stock: int = Form(...),
    db: Session = Depends(get_db),
):
    book = db.query(Bookstore).filter(Bookstore.id == student_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    book.book_name = book_name
    book.author = author
    book.catagory = catagory
    book.price = price
    book.stock = stock
    db.commit()
    db.refresh(book)
    return RedirectResponse(url="/", status_code=303)

@app.get("/delete/{student_id}")
def delete_student_page(student_id: int, db: Session = Depends(get_db)):
    book = db.query(Bookstore).filter(Bookstore.id == student_id).first()
    if book:
        db.delete(book)
        db.commit()
    return RedirectResponse(url="/", status_code=303)

# Create Bookstore
@app.post("/students", response_model=BookResponse)
def create_student(book: BookCreate, db: Session = Depends(get_db)):
    new_book = Bookstore(**book.dict())
    db.add(new_book)
    db.commit()
    db.refresh(new_book)
    return new_book


# Get All Students
@app.get("/students", response_model=list[BookResponse])
def get_students(db: Session = Depends(get_db)):
    return db.query(Bookstore).all()


# Get Bookstore by ID
@app.get("/students/{student_id}", response_model=BookResponse)
def get_student(student_id: int, db: Session = Depends(get_db)):
    book = db.query(Bookstore).filter(Bookstore.id == student_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


# Update Bookstore
@app.put("/students/{student_id}", response_model=BookResponse)
def update_student(student_id: int, updated: BookCreate, db: Session = Depends(get_db)):
    book = db.query(Bookstore).filter(Bookstore.id == student_id).first()
    
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    book.book_name = updated.book_name
    book.author = updated.author
    book.catagory = updated.catagory
    book.price = updated.price
    book.stock = updated.stock

    db.commit()
    db.refresh(book)
    return book


# Delete Bookstore
@app.delete("/students/{student_id}")
def delete_student(student_id: int, db: Session = Depends(get_db)):
    book = db.query(Bookstore).filter(Bookstore.id == student_id).first()
    
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    db.delete(book)
    db.commit()

    return {"message": "Book deleted successfully"}