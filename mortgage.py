import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from tracker_core import DEPOSIT_TO_LTV, monthly_mortgage_payment, validate_tracker_data


ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "dataaffordability.csv"
METADATA_PATH = ROOT / "data_metadata.json"


@st.cache_data(max_entries=1)
def load_tracker_data(csv_path, modified_time_ns):
    return validate_tracker_data(pd.read_csv(csv_path))


def format_uk_time(iso_timestamp):
    utc_time = datetime.fromisoformat(iso_timestamp)
    uk_time = utc_time.astimezone(ZoneInfo("Europe/London"))
    return uk_time.strftime("%d %B %Y, %H:%M %Z")


def main():
    st.title("UK Rent-vs-Buy & Affordability Tracker")

    try:
        data = load_tracker_data(str(DATA_PATH), DATA_PATH.stat().st_mtime_ns)
        metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        st.error(
            f"Could not load valid tracker data: {exc} "
            "Run `python fetch_data.py` to refresh it."
        )
        st.stop()

    area = st.selectbox("Local authority", sorted(data["area"].unique()))
    deposit_pct = st.select_slider(
        "Deposit (%)",
        options=list(DEPOSIT_TO_LTV),
        value=25,
    )
    ltv = DEPOSIT_TO_LTV[deposit_pct]
    rate_column = f"mortgage_rate_{ltv}_ltv"

    local = data.loc[data["area"] == area].sort_values("period").copy()
    local["mortgage_monthly"] = local.apply(
        lambda row: monthly_mortgage_payment(
            row["average_house_price"],
            deposit_pct,
            row[rate_column],
        ),
        axis=1,
    )
    local["rent_to_gross_income_pct"] = (
        local["average_rent_monthly"] * 12 / local["gross_annual_earnings"] * 100
    )

    monthly_costs = local.set_index("period").rename(
        columns={
            "average_rent_monthly": "Rent",
            "mortgage_monthly": "Mortgage (principal + interest)",
        }
    )[["Rent", "Mortgage (principal + interest)"]]
    st.subheader("Monthly rent and estimated mortgage payment (£)")
    st.line_chart(
        monthly_costs,
        alt="Monthly rent and estimated mortgage payments over time",
    )

    rent_share = local.set_index("period").rename(
        columns={"rent_to_gross_income_pct": "Rent / gross earnings"}
    )[["Rent / gross earnings"]]
    st.subheader("Rent as a share of gross annual earnings (%)")
    st.line_chart(
        rent_share,
        alt="Monthly rent as a share of gross annual earnings over time",
    )

    latest = local.iloc[-1]
    source_periods = pd.DataFrame(
        [
            {"Measure": "Rent", "Observation period": latest["rent_period"].strftime("%B %Y")},
            {
                "Measure": "House price",
                "Observation period": latest["house_price_period"].strftime("%B %Y"),
            },
            {
                "Measure": "Gross annual earnings",
                "Observation period": latest["earnings_period"].strftime("%B %Y"),
            },
            {
                "Measure": f"Mortgage rate ({ltv}% LTV)",
                "Observation period": latest["mortgage_rate_period"].strftime("%B %Y"),
            },
        ]
    )
    st.subheader("Reporting periods for the latest chart point")
    st.dataframe(
        source_periods,
        hide_index=True,
        width="stretch",
        alt="Reporting periods for the latest housing affordability data",
    )

    st.caption(
        "Mortgage payments are estimates of principal and interest over 25 years; "
        "they exclude maintenance, taxes, fees, insurance, and other ownership costs. "
        f"The selected {deposit_pct}% deposit uses the Bank of England's {ltv}% LTV "
        "two-year fixed-rate series. Rent affordability uses median gross annual "
        "full-time employee earnings, not household or take-home income. "
        "When a source has no new monthly observation, the latest published value is carried forward."
    )

    with st.expander("Data sources and refresh status"):
        st.write(
            f"Last successful refresh: "
            f"{format_uk_time(metadata['updated_at_utc'])}"
        )
        for source in metadata["sources"].values():
            st.markdown(
                f"- [{source['name']}]({source['url']}) — "
                f"latest observation: {source['latest_observation']}; "
                f"last checked: {format_uk_time(source['last_checked_utc'])}"
            )


if __name__ == "__main__":
    main()
