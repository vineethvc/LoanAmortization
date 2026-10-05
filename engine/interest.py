from decimal import Decimal, ROUND_HALF_UP

def monthly_interest(
    outstanding,
    emi,
    rate_segments,
    days_in_month,
    prepayments,
    emi_day=5,
):
    interest = 0.0
    prepayments_by_day = {}
    for prepayment in prepayments:
        day = prepayment.date.day
        prepayments_by_day[day] = prepayments_by_day.get(day, 0) + prepayment.amount

    principal = outstanding

    for start_day, end_day, rate in rate_segments:
        r = rate / 100 / 365

        for day in range(start_day, end_day + 1):
            if day == emi_day:
                principal = max(principal - emi, 0)
            principal = max(principal - prepayments_by_day.get(day, 0), 0)

            interest += principal * r

    return int(Decimal(str(interest)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

