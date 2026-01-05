import streamlit as st
from datetime import date

from engine.models import Loan, RateChange, EMIChange, Prepayment
from engine.schedule import compute_schedule
#
# from auth import check_password
from storage import init_db, save_scenario, load_scenario, list_scenarios
import altair as alt

# --------------------------------------------------
# Setup
# --------------------------------------------------

st.set_page_config(layout="wide")
st.title("Loan Amortization Simulator")

init_db()

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
        emi = emi * (1 + step) if emi < (base_emi*2) else int(base_emi*2)

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

principal = st.number_input("Principal", value=6_240_344, step=100_000)
base_emi = st.number_input("Base EMI", value=51_000, step=100)
start_date = st.date_input("Loan Start Date", value=date(2025, 7, 1))
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
    rate = st.number_input("Rate (%)", step=0.1, format="%.2f")
    eff_date = st.date_input("Effective From", value=start_date)
    add_rate = st.form_submit_button("Add Rate")

if add_rate:
    st.session_state.rates.append(RateChange(eff_date, rate))
    st.rerun()

for i, r in enumerate(sorted(st.session_state.rates, key=lambda x: x.effective_date)):
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

with st.form("add_emi"):
    emi_amt = st.number_input("EMI Amount", step=100)
    eff_date = st.date_input("Effective From", value=start_date)
    add_emi = st.form_submit_button("Add EMI Change")

with st.form("generate_emi"):
    emi_amt_step = st.number_input("EMI Amount", step=100)
    step_up_percent = st.number_input("Step Up", step=0.1)
    eff_date = st.date_input("Effective From", value=start_date)
    generate_emi = st.form_submit_button("Generate EMI Rates")

if add_emi:
    st.session_state.emis[eff_date] = {
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
    p_date = st.date_input("Prepayment Date")
    p_amt = st.number_input("Amount", min_value=0, step=10_000)
    add_prepay = st.form_submit_button("Add Prepayment")

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
scenario_name = st.text_input("Scenario name")

col1, col2 = st.columns(2)

if col1.button("💾 Save"):
    if not can_edit:
        st.warning("Enter password to save.")
    elif scenario_name:
        payload = {
            "principal": principal,
            "start_date": start_date.isoformat(),
            "rates": [{"date": r.effective_date.isoformat(), "rate": r.rate} for r in st.session_state.rates],
            "emis": [
                        {
                            "date": d.isoformat(),
                            "amount": v["amount"],
                            "auto_gen": v["auto_gen"]
                        }
                        for d, v in st.session_state.emis.items()
                    ],
            "prepays": [{"date": p.date.isoformat(), "amount": p.amount} for p in st.session_state.prepays],
        }
        save_scenario(scenario_name, payload)
        st.success("Saved")

available = list_scenarios()
selected = col2.selectbox("Load scenario", [""] + available)

if selected:
    data = load_scenario(selected)
    st.session_state.rates = [RateChange(date.fromisoformat(r["date"]), r["rate"]) for r in data["rates"]]
    st.session_state.emis =  {
                                date.fromisoformat(e["date"]): {
                                    "amount": e["amount"],
                                    "auto_gen": e.get("auto_gen", False)
                                }
                                for e in data["emis"]
                            }

    st.session_state.prepays = [Prepayment(date.fromisoformat(p["date"]), p["amount"]) for p in data["prepays"]]
    st.rerun()

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

st.subheader("Amortization Schedule")
st.dataframe(df, width='stretch')

baseline_df = compute_schedule(
    loan=loan,
    rate_changes=sorted(st.session_state.rates, key=lambda r: r.effective_date),
    emi_changes=[
    EMIChange(d, v["amount"], v["auto_gen"])
    for d, v in generate_stepup_emis(
        start_date=start_date,
        base_emi=51_000,
        years=10,
        step=0
    ).items()
],
    prepayments=[],  # no prepayments
)


comparison_df = (
    baseline_df[["Month", "Outstanding"]]
    .rename(columns={"Outstanding": "Baseline Outstanding"})
    .merge(
        df[["Month", "Outstanding"]]
        .rename(columns={"Outstanding": "Scenario Outstanding"}),
        on="Month",
        how="outer"
    )
    .set_index("Month")
)


comparison_df["Scenario Outstanding"] = (
    comparison_df["Scenario Outstanding"]
    .fillna(0)
)

chart_df = comparison_df.reset_index().melt(
    id_vars="Month",
    value_vars=["Baseline Outstanding", "Scenario Outstanding"],
    var_name="Type",
    value_name="Outstanding"
)

chart = alt.Chart(chart_df).mark_line(strokeWidth=3).encode(
    x="Month:T",
    y="Outstanding:Q",
    color=alt.Color(
        "Type:N",
        scale=alt.Scale(
            domain=["Baseline Outstanding", "Scenario Outstanding"],
            range=["#d62728", "#2ca02c"]  # red, green
        ),
        legend=alt.Legend(title="Schedule")
    )
).properties(
    width="container",
    height=400,
    title="Outstanding Balance: Baseline vs Scenario"
)

st.altair_chart(chart, width='stretch')

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


