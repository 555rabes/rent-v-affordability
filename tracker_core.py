import math

import pandas as pd


RATE_COLUMNS = [
    "mortgage_rate_60_ltv",
    "mortgage_rate_75_ltv",
    "mortgage_rate_85_ltv",
    "mortgage_rate_90_ltv",
    "mortgage_rate_95_ltv",
]

VALUE_COLUMNS = [
    "average_rent_monthly",
    "average_house_price",
    "gross_annual_earnings",
    *RATE_COLUMNS,
]

PERIOD_COLUMNS = [
    "period",
    "rent_period",
    "house_price_period",
    "earnings_period",
    "mortgage_rate_period",
]

REQUIRED_COLUMNS = ["area", *PERIOD_COLUMNS, *VALUE_COLUMNS]
DEPOSIT_TO_LTV = {5: 95, 10: 90, 15: 85, 25: 75, 40: 60}


def monthly_mortgage_payment(price, deposit_pct, annual_rate_pct, term_years=25):
    values = (price, deposit_pct, annual_rate_pct, term_years)
    if not all(math.isfinite(float(value)) for value in values):
        raise ValueError("Mortgage inputs must be finite numbers.")
    if price <= 0 or not 0 <= deposit_pct < 100:
        raise ValueError("Price must be positive and deposit must be from 0 to 99%.")
    if annual_rate_pct < 0 or term_years <= 0:
        raise ValueError("Rate cannot be negative and term must be positive.")

    loan = price * (1 - deposit_pct / 100)
    monthly_rate = annual_rate_pct / 100 / 12
    months = term_years * 12

    if monthly_rate == 0:
        return loan / months

    return loan * monthly_rate / (1 - (1 + monthly_rate) ** -months)


def validate_tracker_data(data):
    missing_columns = sorted(set(REQUIRED_COLUMNS) - set(data.columns))
    if missing_columns:
        raise ValueError(f"Missing required data columns: {', '.join(missing_columns)}")
    if data.empty:
        raise ValueError("The affordability dataset contains no rows.")

    checked = data[REQUIRED_COLUMNS].copy()
    checked["area"] = checked["area"].astype("string").str.strip()
    if checked["area"].isna().any() or checked["area"].eq("").any():
        raise ValueError("Area names must not be blank.")

    for column in PERIOD_COLUMNS:
        checked[column] = pd.to_datetime(checked[column], errors="coerce")
        if checked[column].isna().any():
            raise ValueError(f"Column '{column}' contains missing or invalid dates.")

    for column in VALUE_COLUMNS:
        checked[column] = pd.to_numeric(checked[column], errors="coerce")
        if checked[column].isna().any():
            raise ValueError(f"Column '{column}' contains missing or non-numeric values.")
        if not checked[column].map(math.isfinite).all():
            raise ValueError(f"Column '{column}' contains non-finite numbers.")

    for column in ("average_rent_monthly", "average_house_price", "gross_annual_earnings"):
        if checked[column].le(0).any():
            raise ValueError(f"Column '{column}' must contain positive values.")

    duplicate_rows = checked.duplicated(["area", "period"], keep=False)
    if duplicate_rows.any():
        duplicate = checked.loc[duplicate_rows, ["area", "period"]].iloc[0]
        raise ValueError(
            f"Duplicate area/month row for {duplicate['area']} on "
            f"{duplicate['period']:%Y-%m-%d}."
        )

    return checked.sort_values(["area", "period"]).reset_index(drop=True)
