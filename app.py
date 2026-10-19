import streamlit as st
from datetime import date
import pandas as pd

from engine.models import Loan, RateChange, EMIChange, Prepayment
from engine.schedule import compute_schedule
from engine.scenarios import schedule_from_payload
#
from auth import check_password
from storage import init_db, save_scenario, load_scenario, list_scenarios
import altair as alt

# --------------------------------------------------
# Setup
# --------------------------------------------------

st.set_page_config(layout="wide")
st.title("Loan Amortization Simulator")

init_db()

DEFAULT_SCENARIO = "current_save"

def apply_scenario(data, name):
    st.session_state.principal = data["principal"]
    st.session_state.base_emi = data["base_emi"]
    st.session_state.start_date = date.fromisoformat(data["start_date"])
    st.session_state.rates = [
        RateChange(date.fromisoformat(item["date"]), item["rate"])
        for item in data["rates"]
    ]
    st.session_state.emis = {
        date.fromisoformat(item["date"]): {
            "amount": item["amount"],
            "auto_gen": item.get("auto_gen", False),
        }
        for item in data["emis"]
    }
    st.session_state.prepays = [
        Prepayment(date.fromisoformat(item["date"]), item["amount"])
        for item in data["prepays"]
    ]
    st.session_state.loaded_scenario = name
    st.session_state.scenario_name = name


def load_selected_scenario():
    name = st.session_state.scenario_to_load
    if name:
        data = load_scenario(name)
        if data:
            apply_scenario(data, name)


if "startup_loaded" not in st.session_state:
    st.session_state.startup_loaded = True

    available = list_scenarios()
    if DEFAULT_SCENARIO in available:
        apply_scenario(load_scenario(DEFAULT_SCENARIO), DEFAULT_SCENARIO)
    else:
        st.session_state.principal = 5000000
        st.session_state.base_emi = 45000
        st.session_state.start_date = date(2025, 7, 1)
        st.session_state.scenario_name = DEFAULT_SCENARIO
# --------------------------------------------------
# Helpers
# --------------------------------------------------

def generate_stepup_emis(start_date, base_emi, years=10, step=0.10):
    emis = {}
    emi = base_emi
    auto_gen = True if step == 0 else False

    for y in range(years):
        eff = date(start_date.year + y, 1, 1)
        emis[eff] = {
            "amount": round(emi, -3),
            "auto_gen": auto_gen
        }
        emi = min(emi * (1 + step), base_emi * 2)

    return emis


# --------------------------------------------------
# Session state
# --------------------------------------------------

if "rates" not in st.session_state:
    st.session_state.rates = []

if "emis" not in st.session_state:
    # dict[date] -> {"amount": float, "auto_gen": bool}
    st.session_state.emis = {}

if "prepays" not in st.session_state:
    st.session_state.prepays = []

# --------------------------------------------------
# Loan basics
# --------------------------------------------------

st.subheader("Loan Basics")

c1, c2, c3 = st.columns(3)

with c1:
    principal = st.number_input(
        "Principal",
        step=100_000,
        key="principal"
    )

with c2:
    base_emi = st.number_input(
        "Base EMI",
        step=100,
        key="base_emi"
    )

with c3:
    start_date = st.date_input(
        "Loan Start Date",
        key="start_date"
    )

emi_day = 5

loan = Loan(principal=principal, start_date=start_date, emi_day=emi_day)

# --------------------------------------------------
# Seed defaults ONCE
# --------------------------------------------------

if not st.session_state.rates:
    st.session_state.rates.append(RateChange(start_date, 7.6))

if not st.session_state.emis:
    st.session_state.emis = generate_stepup_emis(
        start_date=start_date,
        base_emi=base_emi,
        years=10,
        step=0
    )


# --------------------------------------------------
# Interest rate editor
# --------------------------------------------------

st.subheader("Interest Rate Changes")

with st.form("add_rate"):
    c1, c2, c3 = st.columns([2, 2, 1])

    with c1:
        rate = st.number_input("Rate (%)", step=0.1, value=7.6, format="%.2f", key="rate_value")
    with c2:
        eff_date = st.date_input("Effective From", value=date.today(), key="rate_date")
    with c3:
        st.write("")
        add_rate = st.form_submit_button("Add Rate")

if add_rate:
    st.session_state.rates.append(RateChange(eff_date, rate))
    st.rerun()

for i, r in sorted(
    enumerate(st.session_state.rates), key=lambda entry: entry[1].effective_date
):
    c1, c2, c3 = st.columns([3, 3, 1])
    c1.write(r.effective_date)
    c2.write(f"{r.rate:.2f}%")
    if c3.button("❌", key=f"del_rate_{i}") and len(st.session_state.rates) > 1:
        st.session_state.rates.pop(i)
        st.rerun()

# --------------------------------------------------
# EMI editor (manual overrides)
# --------------------------------------------------

st.subheader("EMI Changes (Overrides Allowed)")
c1_emi, c2_emi = st.columns(2)
with c1_emi:
    with st.form("add_emi"):
        emi_amt = st.number_input("EMI Amount",value=base_emi, step=100)
        eff_date_add = st.date_input("Effective From", value=start_date)
        add_emi = st.form_submit_button("Add EMI Change")
with c2_emi:
    with st.form("generate_emi"):
        gen_c1, gen_c2 = st.columns(2)
        with gen_c1:
            emi_amt_step = st.number_input("EMI Amount",value=base_emi, step=100)
        with gen_c2:
            step_up_percent = st.number_input("Step Up", step=0.1)
        eff_date = st.date_input("Effective From", value=start_date)
        generate_emi = st.form_submit_button("Generate EMI Rates")

if add_emi:
    print(f"Saving emi {emi_amt} for {eff_date_add}")
    st.session_state.emis[eff_date_add] = {
        "amount": emi_amt,
        "auto_gen": False
    }
    st.rerun()

if generate_emi:
    generated = generate_stepup_emis(start_date, emi_amt_step, 10, step_up_percent)
    for d, v in generated.items():
        # manual overrides win
        if d not in st.session_state.emis or st.session_state.emis[d]["auto_gen"]:
            st.session_state.emis[d] = v
    st.rerun()


for eff_date in sorted(st.session_state.emis):
    e = st.session_state.emis[eff_date]
    if not e["auto_gen"]:
        c1, c2, c3 = st.columns([3, 3, 1])
        c1.write(eff_date)
        c2.write(f"{e['amount']:,.0f}")
        if c3.button("❌", key=f"del_emi_{eff_date}") and len(st.session_state.emis) > 1:
            del st.session_state.emis[eff_date]
            st.rerun()

st.markdown("### EMI Utilities")

if st.button("🔁 Reset Auto-Generated EMIs"):
    regenerated = generate_stepup_emis(
        start_date=start_date,
        base_emi=base_emi,
        years=10,
        step=0
    )

    for d, v in regenerated.items():
        # overwrite only auto-generated entries
        if d not in st.session_state.emis or not st.session_state.emis[d]["auto_gen"]:
            st.session_state.emis[d] = v

    st.success("Auto-generated EMIs reset. Manual overrides preserved.")
    st.rerun()

# --------------------------------------------------
# Prepayments
# --------------------------------------------------

st.subheader("Prepayments")

with st.form("add_prepay"):
    c1, c2, c3 = st.columns([3, 3, 1])

    with c1:
        p_date = st.date_input(
            "Prepayment Date",
            value=st.session_state.get("next_prepay_date", date.today()),
            label_visibility="visible"
        )

    with c2:
        p_amt = st.number_input(
            "Amount",
            min_value=0,
            step=10_000
        )

    with c3:
        st.write("")  # vertical alignment spacer
        st.write("")
        add_prepay = st.form_submit_button("Add")

if add_prepay and p_amt > 0:
    st.session_state.prepays.append(Prepayment(p_date, p_amt))
    st.rerun()

for i, p in enumerate(sorted(st.session_state.prepays, key=lambda x: x.date)):
    c1, c2, c3 = st.columns([3, 3, 1])
    c1.write(p.date)
    c2.write(f"{p.amount:,.0f}")
    if c3.button("❌", key=f"del_prepay_{i}"):
        st.session_state.prepays.pop(i)
        st.rerun()

# --------------------------------------------------
# Persistence (password-gated)
# --------------------------------------------------

st.subheader("Persistence")

can_edit = check_password()

c1_save, c2_save = st.columns([2, 2])

if "scenario_name" not in st.session_state:
    st.session_state.scenario_name = st.session_state.get("loaded_scenario", DEFAULT_SCENARIO)

with c1_save:
    scenario_name = st.text_input("Scenario name", key="scenario_name").strip()
    st.caption("Save as current_save to load this plan automatically next time.")

    if st.button("💾 Save"):
        if not can_edit:
            st.warning("Enter password to save.")
        elif not scenario_name:
            st.error("Enter a scenario name before saving.")
        else:
            payload = {
                "principal": principal,
                "base_emi": base_emi,
                "start_date": start_date.isoformat(),
                "rates": [
                    {"date": r.effective_date.isoformat(), "rate": r.rate}
                    for r in st.session_state.rates
                ],
                "emis": [
                    {
                        "date": d.isoformat(),
                        "amount": v["amount"],
                        "auto_gen": v["auto_gen"]
                    }
                    for d, v in st.session_state.emis.items()
                ],
                "prepays": [
                    {"date": p.date.isoformat(), "amount": p.amount}
                    for p in st.session_state.prepays
                ],
            }
            save_scenario(scenario_name, payload)
            st.session_state.loaded_scenario = scenario_name
            st.success(f"Saved as {scenario_name}.")

with c2_save:
    available = list_scenarios()
    selected = st.selectbox("Saved scenario", [""] + available, key="scenario_to_load")
    st.button("Load scenario", on_click=load_selected_scenario, disabled=not selected)


# --------------------------------------------------
# Compute & output
# --------------------------------------------------

df = compute_schedule(
    loan=loan,
    rate_changes=sorted(st.session_state.rates, key=lambda r: r.effective_date),
    emi_changes=sorted(
                    [EMIChange(d, v["amount"], v["auto_gen"]) for d, v in st.session_state.emis.items()],
                    key=lambda e: e.effective_date
                ),
    prepayments=sorted(st.session_state.prepays, key=lambda p: p.date),
)

st.subheader("Repayment Schedule")
for year, yearly_df in df.groupby(df["Month"].map(lambda month: month.year), sort=True):
    closing_balance = yearly_df.iloc[-1]["Outstanding"]
    with st.expander(
        f"{year} - {len(yearly_df)} months - closing balance ₹{closing_balance:,.0f}",
        expanded=False,
    ):
        st.dataframe(
            yearly_df.reset_index(drop=True),
            width="stretch",
            height=40 * (len(yearly_df) + 1) + 16,
            hide_index=True,
            column_config={
                "Outstanding": st.column_config.NumberColumn(width="medium"),
            },
        )

baseline_df = compute_schedule(
    loan=loan,
    rate_changes=sorted(st.session_state.rates, key=lambda r: r.effective_date),
    emi_changes=[
        EMIChange(start_date, base_emi, False)
    ],
    prepayments=[]
)


st.subheader("Balance Comparison")
comparison_names = st.multiselect(
    "Compare saved scenarios",
    available,
    default=[name for name in available if name != st.session_state.get("loaded_scenario")],
)


def chart_rows(schedule, plan_name):
    return schedule[["Month", "Outstanding"]].assign(Plan=plan_name)


chart_frames = [
    chart_rows(baseline_df, "Fixed EMI baseline"),
    chart_rows(df, "Current editor"),
]
for name in comparison_names:
    payload = load_scenario(name)
    if payload:
        chart_frames.append(chart_rows(schedule_from_payload(payload), name))

chart_df = pd.concat(chart_frames, ignore_index=True)

chart = alt.Chart(chart_df).mark_line(strokeWidth=3).encode(
    x=alt.X("Month:T", title="Month"),
    y=alt.Y("Outstanding:Q", title="Outstanding (₹)"),
    color=alt.Color("Plan:N", title="Plan"),
    tooltip=[
        alt.Tooltip("Month:T", title="Month", format="%b %Y"),
        alt.Tooltip("Plan:N", title="Plan"),
        alt.Tooltip("Outstanding:Q", title="Outstanding (₹)", format=",.0f"),
    ],
).properties(
    width="container",
    height=400,
    title="Outstanding balance by plan"
)

st.altair_chart(chart, width='stretch')
st.caption("Each saved plan starts on its own start date; the chart does not add zero balances before that date.")

def impact_metrics(baseline_df, scenario_df):
    baseline_interest = baseline_df["Interest"].sum()
    scenario_interest = scenario_df["Interest"].sum()

    interest_saved = baseline_interest - scenario_interest

    baseline_months = len(baseline_df)
    scenario_months = len(scenario_df)

    months_saved = baseline_months - scenario_months

    return {
        "interest_saved": round(interest_saved, 2),
        "months_saved": months_saved,
        "baseline_months": baseline_months,
        "scenario_months": scenario_months,
    }


impact = impact_metrics(baseline_df, df)

st.subheader("Impact Analysis")
st.caption("Current editor compared with the fixed EMI baseline above.")

c1, c2, c3 = st.columns(3)

c1.metric(
    "Interest Saved",
    f"₹{impact['interest_saved']:,.0f}"
)

c2.metric(
    "Loan Tenure Reduced",
    f"{impact['months_saved']} months"
)

c3.metric(
    "Scenario Tenure",
    f"{impact['scenario_months']} months"
)


