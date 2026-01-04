from dataclasses import dataclass
from datetime import date

@dataclass
class RateChange:
    effective_date: date
    rate: float  # annual %

@dataclass
class EMIChange:
    effective_date: date
    amount: float
    auto_gen: bool

@dataclass
class Prepayment:
    date: date
    amount: float

@dataclass
class Loan:
    principal: float
    start_date: date
    emi_day: int = 5
