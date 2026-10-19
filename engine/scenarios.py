from datetime import date

from .models import EMIChange, Loan, Prepayment, RateChange
from .schedule import compute_schedule


def schedule_from_payload(payload):
    """Calculate a saved scenario from its own start date and loan balance."""
    loan = Loan(
        principal=payload["principal"],
        start_date=date.fromisoformat(payload["start_date"]),
        emi_day=5,
    )
    rates = [
        RateChange(date.fromisoformat(item["date"]), item["rate"])
        for item in payload["rates"]
    ]
    emis = [
        EMIChange(
            date.fromisoformat(item["date"]),
            item["amount"],
            item.get("auto_gen", False),
        )
        for item in payload["emis"]
    ]
    prepayments = [
        Prepayment(date.fromisoformat(item["date"]), item["amount"])
        for item in payload["prepays"]
    ]
    return compute_schedule(loan, rates, emis, prepayments)
