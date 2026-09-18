from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.database import SessionLocal
from app.models.bowl_wash_order import (
    BOWL_WASH_ACTIVE_STATUSES,
    BowlWashOrder,
)
from app.models.mill import Mill
from app.serializers import bowl_wash_order_json
from app.utils import error, normalize_datetime

bp = Blueprint("bowl_wash_orders", __name__, url_prefix="/api/bowl-wash-orders")

# 合法流转：open → washing → done；任意非终态可 → void
TRANSITIONS = {
    "start": {"from": "open", "to": "washing"},
    "finish": {"from": "washing", "to": "done"},
    "void": {"from": BOWL_WASH_ACTIVE_STATUSES, "to": "void"},
}


def _validate_create(body: dict) -> tuple[int | None, str | None, dict | None]:
    mill_id = int(body.get("millId") or 0)
    if mill_id <= 0:
        return None, "请选择研磨机", None

    reason = str(body.get("reason", "")).strip()
    if not reason:
        return None, "洗机原因不能为空", None

    planned_at_raw = str(body.get("plannedAt", "")).strip()
    if not planned_at_raw:
        return None, "计划时间不能为空", None

    operator_name = str(body.get("operatorName", "")).strip()
    if not operator_name:
        return None, "操作员不能为空", None

    return (
        mill_id,
        None,
        {
            "reason": reason,
            "planned_at": normalize_datetime(planned_at_raw),
            "operator_name": operator_name,
        },
    )


@bp.get("")
@jwt_required()
def list_orders():
    mill_id = request.args.get("millId", type=int)
    status = request.args.get("status", type=str)

    db = SessionLocal()
    try:
        q = db.query(BowlWashOrder)
        if mill_id:
            q = q.filter(BowlWashOrder.mill_id == mill_id)
        if status:
            q = q.filter(BowlWashOrder.status == status)
        rows = q.order_by(
            BowlWashOrder.planned_at.desc(), BowlWashOrder.id.desc()
        ).all()
        return jsonify([bowl_wash_order_json(r) for r in rows])
    finally:
        db.close()


@bp.get("/<int:item_id>")
@jwt_required()
def get_order(item_id: int):
    db = SessionLocal()
    try:
        row = db.get(BowlWashOrder, item_id)
        if not row:
            return error("洗机工单不存在", 404)
        return jsonify(bowl_wash_order_json(row))
    finally:
        db.close()


@bp.post("")
@jwt_required()
def create_order():
    body = request.get_json(silent=True) or {}
    mill_id, err, fields = _validate_create(body)
    if err:
        return error(err, 400)

    db = SessionLocal()
    try:
        mill = db.get(Mill, mill_id)
        if not mill:
            return error("研磨机不存在", 400)

        # 同一 Mill 同时只允许一个 open / washing
        existing = (
            db.query(BowlWashOrder)
            .filter(
                BowlWashOrder.mill_id == mill_id,
                BowlWashOrder.status.in_(BOWL_WASH_ACTIVE_STATUSES),
            )
            .first()
        )
        if existing:
            return error(
                f"该机台已有未终态洗机工单(# {existing.id}，{existing.status})，请先流转或作废",
                409,
            )

        row = BowlWashOrder(mill_id=mill_id, status="open", **fields)
        db.add(row)
        db.commit()
        db.refresh(row)
        return jsonify(bowl_wash_order_json(row)), 201
    finally:
        db.close()


@bp.post("/<int:item_id>/transitions")
@jwt_required()
def transition_order(item_id: int):
    body = request.get_json(silent=True) or {}
    action = str(body.get("action", "")).strip()
    if action not in TRANSITIONS:
        return error("无效流转动作，应为 start / finish / void", 400)

    rule = TRANSITIONS[action]
    db = SessionLocal()
    try:
        row = db.get(BowlWashOrder, item_id)
        if not row:
            return error("洗机工单不存在", 404)

        allowed_from = rule["from"]
        if row.status not in (
            allowed_from if isinstance(allowed_from, tuple) else (allowed_from,)
        ):
            return error(
                f"当前状态 {row.status} 不允许 {action}（done / void 为终态）", 409
            )

        mill = db.get(Mill, row.mill_id)
        now = normalize_datetime("")

        if action == "start":
            # 开始洗机时机台必须处于 wash；可显式联动置 wash
            if mill.status != "wash":
                if body.get("setMillWash"):
                    mill.status = "wash"
                else:
                    return error(
                        "机台当前不是 wash 状态，请先在研磨机页面置为清洗，"
                        "或勾选“联动置机台为清洗”后再开始",
                        409,
                    )
            row.started_at = now

        if action == "finish":
            row.finished_at = now

        if action == "void":
            row.finished_at = now

        row.status = rule["to"]
        db.commit()
        db.refresh(row)
        return jsonify(bowl_wash_order_json(row))
    finally:
        db.close()
