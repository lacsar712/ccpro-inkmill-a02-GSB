from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.database import SessionLocal
from app.models.bowl_wash_order import (
    ACTIVE_BOWL_WASH_STATUSES,
    BowlWashOrder,
)
from app.models.mill import Mill
from app.serializers import bowl_wash_order_json
from app.utils import error, normalize_datetime

bp = Blueprint("bowl_wash_orders", __name__, url_prefix="/api/bowl-wash-orders")


def _validate_create(body: dict) -> tuple[str | None, dict | None]:
    mill_id = int(body.get("millId") or 0)
    if mill_id <= 0:
        return "请选择研磨机", None

    reason = str(body.get("reason", "")).strip()
    if not reason:
        return "洗机原因不能为空", None

    planned_raw = str(body.get("plannedAt", "")).strip()
    if not planned_raw:
        return "计划时间不能为空", None

    operator_name = str(body.get("operatorName", "")).strip()
    if not operator_name:
        return "操作员不能为空", None

    return None, {
        "mill_id": mill_id,
        "reason": reason,
        "planned_at": normalize_datetime(planned_raw),
        "operator_name": operator_name,
    }


@bp.get("")
@jwt_required()
def list_orders():
    mill_filter = request.args.get("millId", type=int)
    db = SessionLocal()
    try:
        query = db.query(BowlWashOrder)
        if mill_filter:
            query = query.filter(BowlWashOrder.mill_id == mill_filter)
        rows = query.order_by(
            BowlWashOrder.planned_at.desc(), BowlWashOrder.id.desc()
        ).all()
        return jsonify([bowl_wash_order_json(r) for r in rows])
    finally:
        db.close()


@bp.post("")
@jwt_required()
def create_order():
    body = request.get_json(silent=True) or {}
    err, data = _validate_create(body)
    if err:
        return error(err, 400)

    db = SessionLocal()
    try:
        mill = db.get(Mill, data["mill_id"])
        if not mill:
            return error("研磨机不存在", 404)

        # 同一 Mill 同时只允许一个 open / washing
        existing = (
            db.query(BowlWashOrder)
            .filter(
                BowlWashOrder.mill_id == data["mill_id"],
                BowlWashOrder.status.in_(ACTIVE_BOWL_WASH_STATUSES),
            )
            .first()
        )
        if existing:
            return error(
                f"该机台已有未终态洗机工单（#{existing.id}，{existing.status}），请先完成或作废",
                409,
            )

        row = BowlWashOrder(status="open", **data)
        db.add(row)
        db.commit()
        db.refresh(row)
        return jsonify(bowl_wash_order_json(row)), 201
    finally:
        db.close()


@bp.post("/<int:item_id>/start")
@jwt_required()
def start_order(item_id: int):
    body = request.get_json(silent=True) or {}
    sync_mill_status = bool(body.get("syncMillStatus"))

    db = SessionLocal()
    try:
        row = db.get(BowlWashOrder, item_id)
        if not row:
            return error("洗机工单不存在", 404)
        if row.status != "open":
            return error(f"仅 open 工单可开始清洗，当前状态：{row.status}", 409)

        mill = db.get(Mill, row.mill_id)
        if mill.status != "wash":
            if not sync_mill_status:
                return error(
                    "研磨机当前不是 wash（清洗）状态：请先在研磨机页面置为 wash，"
                    "或勾选“工单内联动把机台置为 wash”后重试",
                    409,
                )
            # 经接口显式授权的联动：同事务把机台置 wash，再推进工单
            mill.status = "wash"

        row.status = "washing"
        db.commit()
        db.refresh(row)
        return jsonify(bowl_wash_order_json(row))
    finally:
        db.close()


@bp.post("/<int:item_id>/complete")
@jwt_required()
def complete_order(item_id: int):
    db = SessionLocal()
    try:
        row = db.get(BowlWashOrder, item_id)
        if not row:
            return error("洗机工单不存在", 404)
        if row.status != "washing":
            return error(f"仅 washing 工单可完成，当前状态：{row.status}", 409)

        row.status = "done"
        db.commit()
        db.refresh(row)
        return jsonify(bowl_wash_order_json(row))
    finally:
        db.close()


@bp.post("/<int:item_id>/void")
@jwt_required()
def void_order(item_id: int):
    db = SessionLocal()
    try:
        row = db.get(BowlWashOrder, item_id)
        if not row:
            return error("洗机工单不存在", 404)
        if row.status not in ACTIVE_BOWL_WASH_STATUSES:
            return error(f"done / void 为终态，不能作废，当前状态：{row.status}", 409)

        row.status = "void"
        db.commit()
        db.refresh(row)
        return jsonify(bowl_wash_order_json(row))
    finally:
        db.close()
