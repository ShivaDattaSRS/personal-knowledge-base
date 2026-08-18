import os

from dotenv import load_dotenv
from fastapi import (
    Depends,
    FastAPI,
    Form,
    Request,
)
from fastapi.responses import (
    HTMLResponse,
    RedirectResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from auth import (
    SESSION_COOKIE_NAME,
    create_session,
    delete_session,
    get_current_user,
    hash_password,
    verify_password,
)
from database import Base, engine, get_db
from models import Note, User,UserSession


# Load .env file
load_dotenv()


# Create FastAPI application
app = FastAPI(
    title="Personal Knowledge Base"
)


# Create database tables
Base.metadata.create_all(
    bind=engine
)


# Static files
app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static",
)


# HTML templates
templates = Jinja2Templates(
    directory="templates"
)


# Cookie configuration
SECURE_COOKIE = (
    os.getenv(
        "SECURE_COOKIE",
        "false",
    ).lower()
    == "true"
)


# =========================================================
# HOME
# =========================================================

@app.get("/")
def home():
    return RedirectResponse(
        "/dashboard",
        status_code=303,
    )


# =========================================================
# REGISTER
# =========================================================

@app.get(
    "/register",
    response_class=HTMLResponse,
)
def register_page(
    request: Request,
):
    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={
            "request": request,
        },
    )


@app.post("/register")
def register(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    username = username.strip()

    if len(username) < 3:
        return RedirectResponse(
            "/register?error=Username must be at least 3 characters",
            status_code=303,
        )

    if len(password) < 8:
        return RedirectResponse(
            "/register?error=Password must be at least 8 characters",
            status_code=303,
        )

    existing_user = (
        db.query(User)
        .filter(
            User.username == username
        )
        .first()
    )

    if existing_user:
        return RedirectResponse(
            "/register?error=Username already exists",
            status_code=303,
        )

    password_hash = hash_password(
        password
    )

    user = User(
        username=username,
        password_hash=password_hash,
    )

    db.add(user)
    db.commit()

    return RedirectResponse(
        "/login",
        status_code=303,
    )


# =========================================================
# LOGIN
# =========================================================

@app.get(
    "/login",
    response_class=HTMLResponse,
)
def login_page(
    request: Request,
):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "request": request,
        },
    )


@app.post("/login")
def login(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    username = username.strip()

    user = (
        db.query(User)
        .filter(
            User.username == username
        )
        .first()
    )

    if not user:
        return RedirectResponse(
            "/login?error=Invalid username or password",
            status_code=303,
        )

    if not verify_password(
        password,
        user.password_hash,
    ):
        return RedirectResponse(
            "/login?error=Invalid username or password",
            status_code=303,
        )

    # Create server-side session
    session_id = create_session(
        db,
        user.id,
    )

    # Redirect after successful login
    response = RedirectResponse(
        "/dashboard",
        status_code=303,
    )

    # Store session ID inside HTTP-only cookie
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=SECURE_COOKIE,
        samesite="lax",
        max_age=60 * 60,
    )

    return response


# =========================================================
# DASHBOARD
# =========================================================

@app.get(
    "/dashboard",
    response_class=HTMLResponse,
)
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        user = get_current_user(
            request,
            db,
        )
    except Exception:
        return RedirectResponse(
            "/login",
            status_code=303,
        )

    notes = (
        db.query(Note)
        .filter(
            Note.user_id == user.id
        )
        .order_by(
            Note.created_at.desc()
        )
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "request": request,
            "user": user,
            "notes": notes,
        },
    )


# =========================================================
# CREATE NOTE - PAGE
# =========================================================

@app.get(
    "/notes/new",
    response_class=HTMLResponse,
)
def new_note_page(
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        get_current_user(
            request,
            db,
        )
    except Exception:
        return RedirectResponse(
            "/login",
            status_code=303,
        )

    return templates.TemplateResponse(
        request=request,
        name="note_form.html",
        context={
            "request": request,
            "note": None,
        },
    )


# =========================================================
# CREATE NOTE
# =========================================================

@app.post("/notes/new")
def create_note(
    request: Request,
    title: str = Form(...),
    content: str = Form(...),
    db: Session = Depends(get_db),
):
    user = get_current_user(
        request,
        db,
    )

    title = title.strip()
    content = content.strip()

    if not title or not content:
        return RedirectResponse(
            "/notes/new?error=Title and content are required",
            status_code=303,
        )

    note = Note(
        title=title,
        content=content,
        user_id=user.id,
    )

    db.add(note)
    db.commit()

    return RedirectResponse(
        "/dashboard",
        status_code=303,
    )


# =========================================================
# EDIT NOTE - PAGE
# =========================================================

@app.get(
    "/notes/{note_id}/edit",
    response_class=HTMLResponse,
)
def edit_note_page(
    note_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_current_user(
        request,
        db,
    )

    note = (
        db.query(Note)
        .filter(
            Note.id == note_id,
            Note.user_id == user.id,
        )
        .first()
    )

    if not note:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "request": request,
                "message": "Note not found",
            },
            status_code=404,
        )

    return templates.TemplateResponse(
        request=request,
        name="note_form.html",
        context={
            "request": request,
            "note": note,
        },
    )


# =========================================================
# UPDATE NOTE
# =========================================================

@app.post("/notes/{note_id}/edit")
def update_note(
    note_id: int,
    request: Request,
    title: str = Form(...),
    content: str = Form(...),
    db: Session = Depends(get_db),
):
    user = get_current_user(
        request,
        db,
    )

    note = (
        db.query(Note)
        .filter(
            Note.id == note_id,
            Note.user_id == user.id,
        )
        .first()
    )

    if not note:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "request": request,
                "message": "Note not found",
            },
            status_code=404,
        )

    note.title = title.strip()
    note.content = content.strip()

    db.commit()

    return RedirectResponse(
        "/dashboard",
        status_code=303,
    )


# =========================================================
# DELETE NOTE
# =========================================================

@app.post("/notes/{note_id}/delete")
def delete_note(
    note_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_current_user(
        request,
        db,
    )

    note = (
        db.query(Note)
        .filter(
            Note.id == note_id,
            Note.user_id == user.id,
        )
        .first()
    )

    if not note:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "request": request,
                "message": "Note not found",
            },
            status_code=404,
        )

    db.delete(note)
    db.commit()

    return RedirectResponse(
        "/dashboard",
        status_code=303,
    )


# =========================================================
# LOGOUT
# =========================================================

@app.post("/logout")
def logout(
    request: Request,
    db: Session = Depends(get_db),
):
    session_id = request.cookies.get(
        SESSION_COOKIE_NAME
    )

    if session_id:
        delete_session(
            db,
            session_id,
        )

    response = RedirectResponse(
        "/login",
        status_code=303,
    )

    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
    )

    return response

# =========================================================
# DELETE USER
#  =========================================================
@app.post("/delete-account")
def delete_account(
    request: Request,
    db: Session = Depends(get_db)
):
    # Find the currently logged-in user
    user = get_current_user(
        request,
        db
    )

    # Delete all notes belonging to this user
    db.query(Note).filter(
        Note.user_id == user.id
    ).delete(
        synchronize_session=False
    )

    # Delete all sessions belonging to this user
    db.query(UserSession).filter(
        UserSession.user_id == user.id
    ).delete(
        synchronize_session=False
    )

    # Delete the user
    db.delete(user)

    # Save all changes
    db.commit()

    # Remove login cookie
    response = RedirectResponse(
        "/register",
        status_code=303
    )

    response.delete_cookie(
        key=SESSION_COOKIE_NAME
    )

    return response