from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import PromoCode, User, WithdrawRequest


def format_admin_stats(db: Session) -> str:
    total_users = db.query(User).count()
    banned = db.query(User).filter_by(is_banned=True).count()
    total_pts = int(db.query(func.coalesce(func.sum(User.points), 0)).scalar() or 0)
    pending_wd = db.query(WithdrawRequest).filter_by(status="pending").count()
    active_promos = db.query(PromoCode).filter_by(active=True).count()
    return (
        "📊 **إحصائيات البوت**\n\n"
        f"👥 المستخدمون: **{total_users}**\n"
        f"🚫 محظورون: **{banned}**\n"
        f"💎 مجموع النقاط (كل الحسابات): **{total_pts}**\n"
        f"📤 طلبات سحب قيد المراجعة: **{pending_wd}**\n"
        f"🎁 أكواد برومو مفعّلة: **{active_promos}**"
    )
