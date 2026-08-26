"""Dashboard Python untuk data mart perjalanan bus antarkota.

Aplikasi membaca langsung CSV fact dan dimension pada ``data-mart/output``.
Tidak ada data sintetis baru atau salinan reporting CSV yang dibuat di sini.
"""

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


APP_DIR = Path(__file__).resolve().parent
PROJECT_DIR = APP_DIR.parents[1]
MART_DIR = PROJECT_DIR / "data-mart" / "output"
SLA_LIMIT_MINUTES = 60


def read_table(relative_path: str, date_columns: tuple[str, ...] = ()) -> pd.DataFrame:
    """Membaca satu tabel data mart dan mengubah kolom tanggal bila diperlukan."""
    table = pd.read_csv(MART_DIR / relative_path)
    for column in date_columns:
        table[column] = pd.to_datetime(table[column])
    return table


@st.cache_data
def load_data_mart() -> dict[str, pd.DataFrame]:
    """Memuat fact dan dimension table yang digunakan oleh dashboard."""
    return {
        "ticket": read_table("facts/fct_ticket_sales.csv"),
        "leg": read_table("facts/fct_passenger_itinerary_leg.csv"),
        "loyalty": read_table("facts/fct_loyalty_transaction.csv"),
        "date": read_table("dimensions/dim_date.csv", ("full_date",)),
        "passenger": read_table("dimensions/dim_passenger.csv"),
        "route": read_table("dimensions/dim_route.csv"),
        "fleet": read_table("dimensions/dim_bus_fleet.csv"),
        "terminal": read_table("dimensions/dim_terminal.csv"),
        "loyalty_type": read_table(
            "dimensions/dim_loyalty_transaction_type.csv"
        ),
    }


def enrich_legs(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Menambahkan atribut rute, armada, terminal, penumpang, dan tanggal."""
    legs = tables["leg"].merge(
        tables["route"][["route_sk", "route_name"]], on="route_sk", how="left"
    )
    legs = legs.merge(
        tables["fleet"][["bus_fleet_sk", "bus_fleet_id", "bus_class"]],
        on="bus_fleet_sk",
        how="left",
    )
    legs = legs.merge(
        tables["terminal"][["terminal_sk", "terminal_name"]].rename(
            columns={
                "terminal_sk": "destination_terminal_sk",
                "terminal_name": "destination_terminal_name",
            }
        ),
        on="destination_terminal_sk",
        how="left",
    )
    legs = legs.merge(
        tables["terminal"][["terminal_sk", "terminal_name"]].rename(
            columns={
                "terminal_sk": "origin_terminal_sk",
                "terminal_name": "origin_terminal_name",
            }
        ),
        on="origin_terminal_sk",
        how="left",
    )
    legs = legs.merge(
        tables["passenger"][["passenger_sk", "passenger_id"]],
        on="passenger_sk",
        how="left",
    )
    return legs.merge(
        tables["date"][["date_sk", "full_date", "is_peak_season"]].rename(
            columns={"date_sk": "scheduled_departure_date_sk"}
        ),
        on="scheduled_departure_date_sk",
        how="left",
    )


def missed_connection_pairs(legs: pd.DataFrame) -> pd.DataFrame:
    """Menghitung missed connection pada pasangan leg masuk dan leg lanjutan."""
    onward = legs.loc[legs["leg_sequence"] > 1].copy()
    previous = legs[["itinerary_id", "leg_sequence", "route_name"]].rename(
        columns={"leg_sequence": "previous_leg_sequence", "route_name": "incoming_route"}
    )
    onward["previous_leg_sequence"] = onward["leg_sequence"] - 1
    pairs = onward.merge(
        previous, on=["itinerary_id", "previous_leg_sequence"], how="inner"
    )
    pairs["route_pair"] = pairs["incoming_route"] + " → " + pairs["route_name"]
    return (
        pairs.groupby(["origin_terminal_name", "route_pair"], as_index=False)
        .agg(
            total_connections=("itinerary_leg_sk", "size"),
            total_missed=("missed_connection_count", "sum"),
        )
        .assign(
            missed_connection_rate=lambda frame: (
                100 * frame["total_missed"] / frame["total_connections"]
            )
        )
        .sort_values(
            ["missed_connection_rate", "total_connections"], ascending=[False, False]
        )
    )


def route_fleet_performance(legs: pd.DataFrame) -> pd.DataFrame:
    """Menghindari penggandaan perjalanan akibat grain per penumpang-leg."""
    trips = (
        legs.groupby(
            ["trip_id", "route_name", "bus_fleet_id", "bus_class"], as_index=False
        )
        .agg(arrival_delay_minutes=("arrival_delay_minutes", "max"))
        .assign(
            sla_breach=lambda frame: (
                frame["arrival_delay_minutes"] > SLA_LIMIT_MINUTES
            ).astype(int)
        )
    )
    result = (
        trips.groupby(["route_name", "bus_fleet_id", "bus_class"], as_index=False)
        .agg(
            total_trips=("trip_id", "size"),
            avg_arrival_delay=("arrival_delay_minutes", "mean"),
            total_sla_breach=("sla_breach", "sum"),
        )
        .assign(
            sla_breach_rate=lambda frame: (
                100 * frame["total_sla_breach"] / frame["total_trips"]
            )
        )
    )
    return result.loc[result["total_trips"] >= 3].sort_values(
        ["sla_breach_rate", "avg_arrival_delay"], ascending=[False, False]
    )


def revenue_leakage(legs: pd.DataFrame) -> pd.DataFrame:
    """Menghitung biaya gangguan yang klaimnya disetujui pada musim sibuk."""
    approved = legs.loc[
        legs["is_peak_season"].eq(True) & legs["claim_status"].eq("Approved")
    ].copy()
    approved["revenue_leakage"] = approved[
        ["rebooking_cost", "refund_amount", "compensation_amount"]
    ].sum(axis=1)
    return (
        approved.groupby("route_name", as_index=False)
        .agg(
            rebooking_cost=("rebooking_cost", "sum"),
            refund_amount=("refund_amount", "sum"),
            compensation_amount=("compensation_amount", "sum"),
            revenue_leakage=("revenue_leakage", "sum"),
        )
        .sort_values("revenue_leakage", ascending=False)
    )


def loyalty_tier_profile(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Menghitung perilaku pembelian dan poin berdasarkan tier saat transaksi."""
    ticket = tables["ticket"].merge(
        tables["passenger"][["passenger_sk", "passenger_id", "loyalty_tier"]],
        on="passenger_sk",
        how="left",
    )
    ticket["gross_ticket_revenue"] = (
        ticket["allocated_base_fare"] - ticket["discount_amount"]
    )
    result = (
        ticket.groupby("loyalty_tier", as_index=False)
        .agg(
            passenger_count=("passenger_id", "nunique"),
            total_bookings=("itinerary_id", "nunique"),
            avg_gross_revenue=("gross_ticket_revenue", "mean"),
            points_earned=("loyalty_points_earned", "sum"),
            points_redeemed=("loyalty_points_redeemed", "sum"),
        )
    )
    result["avg_booking_frequency"] = (
        result["total_bookings"] / result["passenger_count"]
    )
    return result.sort_values("avg_booking_frequency", ascending=False)


def repeat_booking_comparison(
    tables: dict[str, pd.DataFrame], legs: pd.DataFrame
) -> pd.DataFrame:
    """Membandingkan repeat booking pada tingkat natural key penumpang."""
    disruptions = (
        legs.groupby("passenger_id", as_index=False)
        .agg(total_missed=("missed_connection_count", "sum"))
    )
    ticket = tables["ticket"].merge(
        tables["passenger"][["passenger_sk", "passenger_id"]],
        on="passenger_sk",
        how="left",
    )
    bookings = (
        ticket.groupby("passenger_id", as_index=False)
        .agg(booking_frequency=("booking_id", "nunique"))
    )
    comparison = disruptions.merge(bookings, on="passenger_id", how="inner")
    comparison["disruption_status"] = comparison["total_missed"].gt(0).map(
        {True: "Pernah missed connection", False: "Tanpa missed connection"}
    )
    comparison["is_repeat"] = comparison["booking_frequency"].gt(1).astype(int)
    return (
        comparison.groupby("disruption_status", as_index=False)
        .agg(
            passenger_count=("passenger_id", "nunique"),
            avg_booking_frequency=("booking_frequency", "mean"),
            repeat_booking_rate=("is_repeat", "mean"),
        )
        .assign(repeat_booking_rate=lambda frame: 100 * frame["repeat_booking_rate"])
    )


def rupiah(value: float) -> str:
    return "Rp{:,.0f}".format(value).replace(",", ".")


st.set_page_config(page_title="Data Mart Bus Antarkota", layout="wide")
st.title("Perjalanan Bus Antarkota Multi-Leg dan Loyalitas Penumpang")
st.caption("Dashboard Python berbasis fact dan dimension CSV hasil ETL")

tables = load_data_mart()
legs = enrich_legs(tables)

min_date = legs["full_date"].min().date()
max_date = legs["full_date"].max().date()
selected_dates = st.sidebar.date_input(
    "Periode keberangkatan", value=(min_date, max_date), min_value=min_date, max_value=max_date
)
route_options = sorted(legs["route_name"].dropna().unique())
selected_routes = st.sidebar.multiselect("Rute", route_options)

if isinstance(selected_dates, (tuple, list)) and len(selected_dates) == 2:
    start_date, end_date = map(pd.Timestamp, selected_dates)
    legs = legs.loc[legs["full_date"].between(start_date, end_date)]
if selected_routes:
    legs = legs.loc[legs["route_name"].isin(selected_routes)]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Itinerary leg", f"{len(legs):,}".replace(",", "."))
col2.metric("Perjalanan", f"{legs['trip_id'].nunique():,}".replace(",", "."))
col3.metric("Missed connection", f"{int(legs['missed_connection_count'].sum()):,}".replace(",", "."))
col4.metric(
    "Klaim disetujui", f"{int(legs['claim_status'].eq('Approved').sum()):,}".replace(",", ".")
)

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Missed Connection", "Delay dan SLA", "Revenue Leakage", "Loyalty Tier", "Repeat Booking"]
)

with tab1:
    result = missed_connection_pairs(legs).head(10)
    st.plotly_chart(
        px.bar(
            result.sort_values("missed_connection_rate"),
            x="missed_connection_rate",
            y="route_pair",
            color="origin_terminal_name",
            orientation="h",
            labels={"missed_connection_rate": "Missed connection rate (%)", "route_pair": "Pasangan rute"},
        ),
        use_container_width=True,
    )
    st.dataframe(result, hide_index=True, use_container_width=True)

with tab2:
    result = route_fleet_performance(legs).head(15)
    st.plotly_chart(
        px.scatter(
            result,
            x="avg_arrival_delay",
            y="sla_breach_rate",
            size="total_trips",
            color="bus_class",
            hover_name="route_name",
            hover_data=["bus_fleet_id", "total_trips"],
            labels={"avg_arrival_delay": "Rata-rata delay (menit)", "sla_breach_rate": "SLA breach rate (%)"},
        ),
        use_container_width=True,
    )
    st.dataframe(result, hide_index=True, use_container_width=True)

with tab3:
    result = revenue_leakage(legs).head(10)
    st.plotly_chart(
        px.bar(
            result.sort_values("revenue_leakage"),
            x="revenue_leakage",
            y="route_name",
            orientation="h",
            labels={"revenue_leakage": "Revenue leakage (Rp)", "route_name": "Rute"},
        ),
        use_container_width=True,
    )
    if not result.empty:
        st.metric("Revenue leakage pada rute tertinggi", rupiah(result.iloc[0]["revenue_leakage"]))
    st.dataframe(result, hide_index=True, use_container_width=True)

with tab4:
    result = loyalty_tier_profile(tables)
    st.plotly_chart(
        px.bar(
            result,
            x="loyalty_tier",
            y=["points_earned", "points_redeemed"],
            barmode="group",
            labels={"value": "Jumlah poin", "loyalty_tier": "Loyalty tier", "variable": "Jenis poin"},
        ),
        use_container_width=True,
    )
    st.dataframe(result, hide_index=True, use_container_width=True)

with tab5:
    result = repeat_booking_comparison(tables, legs)
    st.plotly_chart(
        px.bar(
            result,
            x="disruption_status",
            y="repeat_booking_rate",
            color="disruption_status",
            text_auto=".2f",
            labels={"repeat_booking_rate": "Repeat booking rate (%)", "disruption_status": "Riwayat gangguan"},
        ),
        use_container_width=True,
    )
    st.dataframe(result, hide_index=True, use_container_width=True)
    st.info(
        "Perbandingan ini menunjukkan asosiasi, bukan hubungan sebab-akibat. "
        "Penumpang yang lebih sering bepergian juga lebih berpeluang mengalami gangguan."
    )
