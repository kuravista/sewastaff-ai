from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import case, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financial_transaction import FinancialTransaction

JAKARTA_TZ = ZoneInfo("Asia/Jakarta")


def _parse_dt(value: str | datetime | None) -> datetime:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        dt = datetime.now(JAKARTA_TZ)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JAKARTA_TZ)
    return dt.astimezone(timezone.utc)


def _period_range(period: str | None) -> tuple[datetime, datetime, str]:
    now = datetime.now(JAKARTA_TZ)
    p = period or "this_month"
    if p == "today":
        start = datetime.combine(now.date(), time.min, tzinfo=JAKARTA_TZ)
        end = start + timedelta(days=1)
        label = "hari ini"
    elif p == "this_week":
        start = datetime.combine((now - timedelta(days=now.weekday())).date(), time.min, tzinfo=JAKARTA_TZ)
        end = start + timedelta(days=7)
        label = "minggu ini"
    elif p == "last_month":
        first_this = datetime(now.year, now.month, 1, tzinfo=JAKARTA_TZ)
        last_month_end = first_this
        month = 12 if now.month == 1 else now.month - 1
        year = now.year - 1 if now.month == 1 else now.year
        start = datetime(year, month, 1, tzinfo=JAKARTA_TZ)
        end = last_month_end
        label = "bulan lalu"
    else:
        start = datetime(now.year, now.month, 1, tzinfo=JAKARTA_TZ)
        if now.month == 12:
            end = datetime(now.year + 1, 1, 1, tzinfo=JAKARTA_TZ)
        else:
            end = datetime(now.year, now.month + 1, 1, tzinfo=JAKARTA_TZ)
        label = "bulan ini"
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc), label


def _fmt_idr(value: int | float | None) -> str:
    return f"Rp{int(value or 0):,}".replace(",", ".")


async def save_finance_transaction(
    db: AsyncSession,
    rental_id: UUID,
    group_id: str,
    sender_id: str | None,
    event,
    extraction: dict,
) -> FinancialTransaction:
    has_image = bool(getattr(event, "media_url", None))
    tx = FinancialTransaction(
        rental_id=rental_id,
        group_id=group_id,
        sender_id=sender_id,
        tx_type=extraction.get("tx_type") or "expense",
        amount_idr=int(extraction.get("amount_idr") or 0),
        currency=extraction.get("currency") or "IDR",
        category=extraction.get("category"),
        merchant=extraction.get("merchant"),
        description=extraction.get("description") or (getattr(event, "message_text", "") or "Transaksi"),
        transaction_date=_parse_dt(extraction.get("transaction_date")),
        source="image" if has_image else "text",
        image_url=getattr(event, "media_url", None) if has_image else None,
        ocr_text=extraction.get("ocr_text"),
        confidence=float(extraction.get("confidence") or 0.7),
        status=extraction.get("status") or "confirmed",
    )
    db.add(tx)
    await db.commit()
    await db.refresh(tx)
    return tx


async def answer_finance_query(db: AsyncSession, rental_id: UUID, group_id: str, query: dict) -> str:
    start, end, label = _period_range(query.get("period"))
    base = [
        FinancialTransaction.rental_id == rental_id,
        FinancialTransaction.group_id == group_id,
        FinancialTransaction.status == "confirmed",
        FinancialTransaction.transaction_date >= start,
        FinancialTransaction.transaction_date < end,
    ]
    metric = query.get("metric") or "summary"

    if metric == "list_transactions":
        limit = min(int(query.get("limit") or 10), 25)
        rows = (await db.execute(
            select(FinancialTransaction).where(*base).order_by(FinancialTransaction.transaction_date.desc()).limit(limit)
        )).scalars().all()
        if not rows:
            return f"Belum ada transaksi tercatat untuk {label}."
        lines = [f"📒 Transaksi {label}:"]
        for tx in rows:
            tgl = tx.transaction_date.astimezone(JAKARTA_TZ).strftime("%d/%m %H:%M")
            sign = "+" if tx.tx_type == "income" else "-" if tx.tx_type in ["expense", "transfer"] else ""
            lines.append(f"• {tgl} {sign}{_fmt_idr(tx.amount_idr)} — {tx.category or 'Lainnya'} — {tx.description}")
        return "\n".join(lines)

    if metric == "top_categories":
        rows = (await db.execute(
            select(FinancialTransaction.category, func.sum(FinancialTransaction.amount_idr).label("total"))
            .where(*base, FinancialTransaction.tx_type == "expense")
            .group_by(FinancialTransaction.category).order_by(desc("total")).limit(5)
        )).all()
        if not rows:
            return f"Belum ada pengeluaran tercatat untuk {label}."
        lines = [f"🏷️ Kategori pengeluaran terbesar {label}:"]
        for cat, total in rows:
            lines.append(f"• {cat or 'Lainnya'}: {_fmt_idr(total)}")
        return "\n".join(lines)

    res = await db.execute(select(
        func.coalesce(func.sum(case((FinancialTransaction.tx_type == "income", FinancialTransaction.amount_idr), else_=0)), 0),
        func.coalesce(func.sum(case((FinancialTransaction.tx_type.in_(["expense", "transfer"]), FinancialTransaction.amount_idr), else_=0)), 0),
    ).where(*base))
    income, expense = res.one()
    profit = int(income or 0) - int(expense or 0)
    if metric == "expense_total":
        return f"💸 Total pengeluaran {label}: *{_fmt_idr(expense)}*."
    if metric == "income_total":
        return f"💰 Total pemasukan {label}: *{_fmt_idr(income)}*."
    if metric == "profit":
        return f"📈 Profit {label}: *{_fmt_idr(profit)}* (pemasukan {_fmt_idr(income)} - pengeluaran {_fmt_idr(expense)})."
    lines = [
        f"📊 Rekap keuangan {label}:",
        f"• Pemasukan: *{_fmt_idr(income)}*",
        f"• Pengeluaran: *{_fmt_idr(expense)}*",
        f"• Profit: *{_fmt_idr(profit)}*",
    ]
    if profit < 0:
        lines.append("")
        lines.append("⚠️ Saldo minus! Pengeluaran melebihi pemasukan.")
    return "\n".join(lines)
