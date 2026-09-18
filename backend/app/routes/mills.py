from decimal import Decimal

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models.bowl_wash_order import ACTIVE_BOWL_WASH_STATUSES, BowlWashOrder
from app.models.mill import MILL_STATUSES, Mill
from app.models.workshop import Workshop
from app.serializers import mill_json
from app.utils import error

bp = Blueprint("mills", __name__, url_prefix="/api/mills")


def _active_wash_map(db, mill_ids: list[int] | None = None) -> dict[int, BowlWashOrder]:
    """每台研磨机至多一个 open / washing 工单，取最新一条作为开放标记。"""
    query = db.query(BowlWashOrder).filter(
        BowlWashOrder.status.in_(ACTIVE_BOWL_WASH_STATUSES)
    )
    if mill_ids is not None:
        query = query.filter(BowlWashOrder.mill_id.in_(mill_ids))
    result: dict[int, BowlWashOrder] = {}
    for order in query.order_by(BowlWashOrder.id.desc()).all():
        result.setdefault(order.mill_id, order)
    return result


def _validate(body: dict) -> str | None:
    workshop_id = int(body.get("workshopId") or 0)
    if workshop_id <= 0:
        return "请选择所属车间"

    mill_code = str(body.get("millCode", "")).strip()
    if not mill_code:
        return "研磨机编号不能为空"

    pigment_base = str(body.get("pigmentBase", "")).strip()
    if not pigment_base:
        return "色浆基料不能为空"

    status = str(body.get("status") or "idle")
    if status not in MILL_STATUSES:
        return "状态无效，应为 grinding / idle / wash"

    db = SessionLocal()
    try:
        if not db.get(Workshop, workshop_id):
            return "所属车间不存在"
    finally:
        db.close()

    return None


@bp.get("")
@jwt_required()
def list_mills():
    db = SessionLocal()
    try:
        rows = db.query(Mill).order_by(Mill.id.desc()).all()
        active_map = _active_wash_map(db, [r.id for r in rows])
        return jsonify([mill_json(r, active_map.get(r.id)) for r in rows])
    finally:
        db.close()


@bp.post("")
@jwt_required()
def create_mill():
    body = request.get_json(silent=True) or {}
    err = _validate(body)
    if err:
        return error(err, 400)

    db = SessionLocal()
    try:
        row = Mill(
            workshop_id=int(body["workshopId"]),
            mill_code=str(body["millCode"]).strip(),
            pigment_base=str(body["pigmentBase"]).strip(),
            bowl_liters=Decimal(str(body.get("bowlLiters", 0))),
            status=str(body.get("status") or "idle"),
        )
        db.add(row)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return error("该车间下研磨机编号已存在", 400)
        db.refresh(row)
        return jsonify(mill_json(row)), 201
    finally:
        db.close()


@bp.put("/<int:item_id>")
@jwt_required()
def update_mill(item_id: int):
    body = request.get_json(silent=True) or {}
    err = _validate(body)
    if err:
        return error(err, 400)

    db = SessionLocal()
    try:
        row = db.get(Mill, item_id)
        if not row:
            return error("研磨机不存在", 404)

        row.workshop_id = int(body["workshopId"])
        row.mill_code = str(body["millCode"]).strip()
        row.pigment_base = str(body["pigmentBase"]).strip()
        row.bowl_liters = Decimal(str(body.get("bowlLiters", 0)))
        row.status = str(body.get("status") or "idle")
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return error("该车间下研磨机编号已存在", 400)
        db.refresh(row)
        return jsonify(mill_json(row))
    finally:
        db.close()


@bp.delete("/<int:item_id>")
@jwt_required()
def delete_mill(item_id: int):
    db = SessionLocal()
    try:
        row = db.get(Mill, item_id)
        if not row:
            return error("研磨机不存在", 404)
        db.delete(row)
        db.commit()
        return jsonify({"ok": True})
    finally:
        db.close()
