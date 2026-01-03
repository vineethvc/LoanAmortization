import pandas as pd
from datetime import date
from calendar import monthrange

from .models import Loan, RateChange, EMIChange, Prepayment
from .interest import monthly_interest


def rate_on_date(dt, rate_changes):
    applicable = [r for r in rate_changes if r.effective_date <= dt]
    if not applicable:
        raise ValueError(f"No rate defined for {dt}")
    return applicable[-1].rate


def emi_on_date(dt, emi_changes):
    applicable = [e for e in emi_changes if e.effective_date <= dt]
    if not applicable:
        raise ValueError(f"No EMI defined for {dt}")
    return applicable[-1].amount


def rate_segments_for_month(month_start, days_in_month, rate_changes):
    """
    Returns list of (start_day, end_day, rate)
    """
    segments = []

    # relevant rate changes within this month
    month_changes = [
        r for r in rate_changes
        if month_start <= r.effective_date < month_start.replace(day=days_in_month)
    ]

    # include the rate active at month start
    current_rate = rate_on_date(month_start, rate_changes)
    current_day = 1

    for rc in sorted(month_changes, key=lambda r: r.effective_date):
        change_day = rc.effective_date.day
        if change_day > current_day:
            segments.append((current_day, change_day - 1, current_rate))
        current_rate = rc.rate
        current_day = change_day

    # final segment till month end
    if current_day <= days_in_month:
        segments.append((current_day, days_in_month, current_rate))

    return segments



def compute_schedule(
    loan: Loan,
    rate_changes: list[RateChange],
    emi_changes: list[EMIChange],
    prepayments: list[Prepayment],
    months: int = 240,
) -> pd.DataFrame:

    rows = []
    outstanding = loan.principal

    rate_changes = sorted(rate_changes, key=lambda r: r.effective_date)
    emi_changes = sorted(emi_changes, key=lambda e: e.effective_date)
    prepayments = sorted(prepayments, key=lambda p: p.date)

    for m in range(months):
        year = loan.start_date.year + (loan.start_date.month - 1 + m) // 12
        month = (loan.start_date.month - 1 + m) % 12 + 1
        month_start = date(year, month, 1)
        days_in_month = monthrange(year, month)[1]

        rate = rate_on_date(month_start, rate_changes)
        emi = emi_on_date(month_start, emi_changes)

        prepay = next(
            (p for p in prepayments if p.date.year == year and p.date.month == month),
            None
        )

        rate_segments = rate_segments_for_month(
            month_start,
            days_in_month,
            rate_changes
        )

        interest = monthly_interest(
            outstanding=outstanding,
            emi=emi,
            rate_segments=rate_segments,
            days_in_month=days_in_month,
            prepay_day=prepay.date.day if prepay else None,
            prepay_amount=prepay.amount if prepay else 0,
            emi_day=loan.emi_day,
        )

        principal_paid = max(emi - interest, 0)
        outstanding = max(
            outstanding - principal_paid - (prepay.amount if prepay else 0),
            0
        )

        rows.append({
            "Month": month_start,
            "Rate (%)": rate,
            "EMI": emi,
            "Interest": round(interest, 2),
            "Principal Paid": round(principal_paid, 2),
            "Prepayment": prepay.amount if prepay else 0,
            "Outstanding": round(outstanding, 2),
        })

        if outstanding <= 0:
            break

    return pd.DataFrame(rows)
