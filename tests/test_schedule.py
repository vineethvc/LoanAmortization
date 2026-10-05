import unittest
from datetime import date

from engine.interest import monthly_interest
from engine.models import EMIChange, Loan, Prepayment, RateChange
from engine.schedule import compute_schedule


class ScheduleTests(unittest.TestCase):
    def test_interest_matches_statement_with_nearest_rupee_rounding(self):
        july = monthly_interest(
            outstanding=6_240_344,
            emi=51_000,
            rate_segments=[(1, 31, 7.6)],
            days_in_month=31,
            prepayments=[],
        )
        september = monthly_interest(
            outstanding=5_972_063,
            emi=56_000,
            rate_segments=[(1, 30, 7.35)],
            days_in_month=30,
            prepayments=[],
        )
        self.assertEqual(july, 39_993)
        self.assertEqual(september, 35_785)

    def test_multiple_prepayments_reduce_interest_from_each_payment_date(self):
        start = date(2026, 9, 1)
        prepayments = [
            Prepayment(date(2026, 9, 10), 1_000),
            Prepayment(date(2026, 9, 20), 2_000),
        ]
        result = compute_schedule(
            Loan(100_000, start, emi_day=5),
            [RateChange(start, 12.0)],
            [EMIChange(start, 10_000, False)],
            prepayments,
            months=1,
        )
        expected_interest = round(
            (100_000 * 4 + 90_000 * 5 + 89_000 * 10 + 87_000 * 11)
            * 0.12 / 365
        )
        self.assertEqual(result.iloc[0]["Interest"], expected_interest)
        self.assertEqual(result.iloc[0]["Prepayment"], 3_000)
        self.assertEqual(
            result.iloc[0]["Outstanding"],
            100_000 - 10_000 - 3_000 + expected_interest,
        )


if __name__ == "__main__":
    unittest.main()
