from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, URLSafeSerializer
from sqlalchemy import desc

from app.config import settings
from app.database import (
    Country,
    SessionLocal,
    Task,
    TransferRequest,
    User,
    get_setting,
    set_setting,
)

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
serializer = URLSafeSerializer(settings.secret_key, salt="admin-session")


def create_admin_app() -> FastAPI:
    app = FastAPI(title="Transfer Bot Admin")
    app.mount("/static", StaticFiles(directory=str(TEMPLATES_DIR / "static")), name="static")

    def get_session(request: Request) -> bool:
        token = request.cookies.get("session")
        if not token:
            return False
        try:
            data = serializer.loads(token)
            return data.get("auth") is True
        except BadSignature:
            return False

    @app.get("/login", response_class=HTMLResponse)
    async def login_page(request: Request):
        if get_session(request):
            return RedirectResponse("/", status_code=302)
        return templates.TemplateResponse("login.html", {"request": request})

    @app.post("/login")
    async def login(request: Request, password: str = Form(...)):
        if password != settings.admin_password:
            return templates.TemplateResponse(
                "login.html", {"request": request, "error": "كلمة المرور غير صحيحة"}
            )
        token = serializer.dumps({"auth": True})
        resp = RedirectResponse("/", status_code=302)
        resp.set_cookie("session", token, httponly=True, samesite="lax")
        return resp

    @app.get("/logout")
    async def logout():
        resp = RedirectResponse("/login", status_code=302)
        resp.delete_cookie("session")
        return resp

    def require_auth(request: Request):
        if not get_session(request):
            return RedirectResponse("/login", status_code=302)
        return None

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request):
        redir = require_auth(request)
        if redir:
            return redir
        db = SessionLocal()
        try:
            stats = {
                "users": db.query(User).count(),
                "pending": db.query(TransferRequest).filter_by(status="pending").count(),
                "tasks": db.query(Task).filter_by(active=True).count(),
                "referral_pts": get_setting(db, "referral_points", "25"),
            }
            recent = (
                db.query(TransferRequest)
                .order_by(desc(TransferRequest.created_at))
                .limit(10)
                .all()
            )
            return templates.TemplateResponse(
                "dashboard.html",
                {"request": request, "stats": stats, "recent": recent},
            )
        finally:
            db.close()

    @app.get("/transfers", response_class=HTMLResponse)
    async def transfers(request: Request):
        redir = require_auth(request)
        if redir:
            return redir
        db = SessionLocal()
        try:
            items = db.query(TransferRequest).order_by(desc(TransferRequest.created_at)).all()
            return templates.TemplateResponse(
                "transfers.html", {"request": request, "items": items}
            )
        finally:
            db.close()

    @app.post("/transfers/{req_id}/status")
    async def transfer_status(req_id: int, status: str = Form(...)):
        db = SessionLocal()
        try:
            req = db.query(TransferRequest).filter_by(id=req_id).first()
            if req:
                req.status = status
                db.commit()
        finally:
            db.close()
        return RedirectResponse("/transfers", status_code=302)

    @app.get("/countries", response_class=HTMLResponse)
    async def countries(request: Request):
        redir = require_auth(request)
        if redir:
            return redir
        db = SessionLocal()
        try:
            items = db.query(Country).order_by(Country.sort_order).all()
            return templates.TemplateResponse(
                "countries.html", {"request": request, "items": items}
            )
        finally:
            db.close()

    @app.post("/countries/add")
    async def country_add(
        name_ar: str = Form(...),
        name_en: str = Form(...),
        point_cost: int = Form(50),
        sort_order: int = Form(0),
    ):
        db = SessionLocal()
        try:
            db.add(
                Country(
                    name_ar=name_ar,
                    name_en=name_en,
                    point_cost=point_cost,
                    sort_order=sort_order,
                    active=True,
                )
            )
            db.commit()
        finally:
            db.close()
        return RedirectResponse("/countries", status_code=302)

    @app.post("/countries/{cid}/toggle")
    async def country_toggle(cid: int):
        db = SessionLocal()
        try:
            c = db.query(Country).filter_by(id=cid).first()
            if c:
                c.active = not c.active
                db.commit()
        finally:
            db.close()
        return RedirectResponse("/countries", status_code=302)

    @app.post("/countries/{cid}/delete")
    async def country_delete(cid: int):
        db = SessionLocal()
        try:
            c = db.query(Country).filter_by(id=cid).first()
            if c:
                db.delete(c)
                db.commit()
        finally:
            db.close()
        return RedirectResponse("/countries", status_code=302)

    @app.get("/tasks", response_class=HTMLResponse)
    async def tasks_page(request: Request):
        redir = require_auth(request)
        if redir:
            return redir
        db = SessionLocal()
        try:
            items = db.query(Task).order_by(Task.sort_order).all()
            return templates.TemplateResponse("tasks.html", {"request": request, "items": items})
        finally:
            db.close()

    @app.post("/tasks/add")
    async def task_add(
        title_ar: str = Form(...),
        title_en: str = Form(...),
        chat_id: str = Form(...),
        invite_link: str = Form(""),
        reward_points: int = Form(10),
        sort_order: int = Form(0),
    ):
        db = SessionLocal()
        try:
            db.add(
                Task(
                    title_ar=title_ar,
                    title_en=title_en,
                    chat_id=chat_id.strip(),
                    invite_link=invite_link.strip() or None,
                    reward_points=reward_points,
                    sort_order=sort_order,
                    active=True,
                )
            )
            db.commit()
        finally:
            db.close()
        return RedirectResponse("/tasks", status_code=302)

    @app.post("/tasks/{tid}/toggle")
    async def task_toggle(tid: int):
        db = SessionLocal()
        try:
            t = db.query(Task).filter_by(id=tid).first()
            if t:
                t.active = not t.active
                db.commit()
        finally:
            db.close()
        return RedirectResponse("/tasks", status_code=302)

    @app.post("/tasks/{tid}/delete")
    async def task_delete(tid: int):
        db = SessionLocal()
        try:
            t = db.query(Task).filter_by(id=tid).first()
            if t:
                db.delete(t)
                db.commit()
        finally:
            db.close()
        return RedirectResponse("/tasks", status_code=302)

    @app.get("/settings", response_class=HTMLResponse)
    async def settings_page(request: Request):
        redir = require_auth(request)
        if redir:
            return redir
        db = SessionLocal()
        try:
            referral = get_setting(db, "referral_points", "25")
            return templates.TemplateResponse(
                "settings.html", {"request": request, "referral_points": referral}
            )
        finally:
            db.close()

    @app.post("/settings")
    async def settings_save(referral_points: int = Form(...)):
        db = SessionLocal()
        try:
            set_setting(db, "referral_points", str(referral_points))
        finally:
            db.close()
        return RedirectResponse("/settings", status_code=302)

    @app.get("/users", response_class=HTMLResponse)
    async def users_page(request: Request):
        redir = require_auth(request)
        if redir:
            return redir
        db = SessionLocal()
        try:
            items = db.query(User).order_by(desc(User.created_at)).limit(200).all()
            return templates.TemplateResponse("users.html", {"request": request, "items": items})
        finally:
            db.close()

    @app.post("/users/{uid}/points")
    async def user_points(uid: int, points: int = Form(...)):
        db = SessionLocal()
        try:
            u = db.query(User).filter_by(id=uid).first()
            if u:
                u.points = points
                db.commit()
        finally:
            db.close()
        return RedirectResponse("/users", status_code=302)

    @app.post("/users/{uid}/add")
    async def user_add_points(uid: int, add_points: int = Form(...)):
        db = SessionLocal()
        try:
            u = db.query(User).filter_by(id=uid).first()
            if u and add_points > 0:
                u.points += add_points
                db.commit()
        finally:
            db.close()
        return RedirectResponse("/users", status_code=302)

    return app
