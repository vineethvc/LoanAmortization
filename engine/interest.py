def monthly_interest(
    outstanding,
    emi,
    rate_segments,
    days_in_month,
    prepay_day,
    prepay_amount,
    emi_day=5,
):
    interest = 0.0

    for start_day, end_day, rate in rate_segments:
        r = rate / 100 / 365

        for day in range(start_day, end_day + 1):
            principal = outstanding

            if day >= emi_day:
                principal = max(principal - emi, 0)

            if prepay_day and day >= prepay_day:
                principal = max(principal - prepay_amount, 0)

            interest += principal * r

    return interest

