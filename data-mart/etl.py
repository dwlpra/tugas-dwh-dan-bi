import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT_DIR / "synthetic-data-generation" / "data" / "raw"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
DIMENSION_DIR = OUTPUT_DIR / "dimensions"
FACT_DIR = OUTPUT_DIR / "facts"
REJECTED_DIR = OUTPUT_DIR / "rejected"


def read_csv(filename):
    with (RAW_DIR / filename).open(newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def write_csv(path, rows, fieldnames=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_timestamp(value):
    return datetime.fromisoformat(value) if value else None


def date_key(value):
    return int(value.strftime("%Y%m%d")) if value else ""


def time_key(value):
    return value.hour * 100 + value.minute if value else ""


def build_temporal_lookup(rows, natural_key, surrogate_key):
    lookup = defaultdict(list)
    for row in rows:
        lookup[row[natural_key]].append({
            "start": date.fromisoformat(row["effective_start_date"]),
            "end": date.fromisoformat(row["effective_end_date"]) if row["effective_end_date"] else None,
            "sk": row[surrogate_key],
        })
    return lookup


def resolve_temporal(lookup, natural_key, event_date):
    for version in lookup[natural_key]:
        if event_date >= version["start"] and (
            version["end"] is None or event_date < version["end"]
        ):
            return version["sk"]
    raise ValueError(f"Versi dimensi tidak ditemukan: {natural_key} pada {event_date}")


def build_date_dimension(timestamps):
    first_date = min(value.date() for value in timestamps if value)
    last_date = max(value.date() for value in timestamps if value)
    rows = []
    current = first_date
    day_names = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
    month_names = [
        "Januari", "Februari", "Maret", "April", "Mei", "Juni",
        "Juli", "Agustus", "September", "Oktober", "November", "Desember",
    ]
    while current <= last_date:
        rows.append({
            "date_sk": int(current.strftime("%Y%m%d")),
            "full_date": current.isoformat(),
            "day_of_month": current.day,
            "day_name": day_names[current.weekday()],
            "week_of_year": current.isocalendar().week,
            "month_number": current.month,
            "month_name": month_names[current.month - 1],
            "quarter_number": (current.month - 1) // 3 + 1,
            "year_number": current.year,
            "is_weekend": current.weekday() >= 5,
            "is_peak_season": current.month in {6, 7, 12},
        })
        current += timedelta(days=1)
    return rows


def build_time_dimension():
    rows = []
    for hour in range(24):
        for minute in range(60):
            if 5 <= hour < 11:
                period = "Pagi"
            elif 11 <= hour < 15:
                period = "Siang"
            elif 15 <= hour < 19:
                period = "Sore"
            else:
                period = "Malam"
            rows.append({
                "time_sk": hour * 100 + minute,
                "full_time": f"{hour:02d}:{minute:02d}:00",
                "hour_number": hour,
                "minute_number": minute,
                "time_period": period,
                "is_peak_hour": hour in {6, 7, 8, 16, 17, 18},
            })
    return rows


def build_passenger_dimension(passengers, histories):
    passenger_by_id = {row["passenger_id"]: row for row in passengers}
    rows = []
    for history in sorted(histories, key=lambda row: (row["passenger_id"], row["effective_start_date"])):
        master = passenger_by_id[history["passenger_id"]]
        rows.append({
            "passenger_sk": len(rows) + 1,
            "passenger_id": history["passenger_id"],
            "passenger_name": master["passenger_name"],
            "email": master["email"],
            "phone": master["phone"],
            "city": master["city"],
            "registration_date": master["registration_date"],
            "loyalty_tier": history["loyalty_tier"],
            "effective_start_date": history["effective_start_date"],
            "effective_end_date": history["effective_end_date"],
            "is_current": not history["effective_end_date"],
        })
    return rows


def build_fleet_dimension(fleets, histories):
    fleet_by_id = {row["bus_fleet_id"]: row for row in fleets}
    histories_by_id = defaultdict(list)
    for row in histories:
        histories_by_id[row["bus_fleet_id"]].append(row)

    rows = []
    for fleet_id in sorted(fleet_by_id):
        master = fleet_by_id[fleet_id]
        versions = histories_by_id.get(fleet_id) or [{
            "bus_fleet_id": fleet_id,
            "bus_class": master["bus_class"],
            "seat_configuration": master["seat_configuration"],
            "seat_capacity": master["seat_capacity"],
            "effective_start_date": "2024-01-01",
            "effective_end_date": "",
        }]
        for version in sorted(versions, key=lambda row: row["effective_start_date"]):
            rows.append({
                "bus_fleet_sk": len(rows) + 1,
                "bus_fleet_id": fleet_id,
                "license_plate": master["license_plate"],
                "bus_class": version["bus_class"],
                "seat_configuration": version["seat_configuration"],
                "seat_capacity": int(version["seat_capacity"]),
                "manufacture_year": int(master["manufacture_year"]),
                "status": master["status"],
                "effective_start_date": version["effective_start_date"],
                "effective_end_date": version["effective_end_date"],
                "is_current": not version["effective_end_date"],
            })
    return rows


def build_terminal_dimension(terminals, histories):
    terminal_by_id = {row["terminal_id"]: row for row in terminals}
    histories_by_id = defaultdict(list)
    for row in histories:
        histories_by_id[row["terminal_id"]].append(row)

    rows = []
    for terminal_id in sorted(terminal_by_id):
        master = terminal_by_id[terminal_id]
        versions = histories_by_id.get(terminal_id) or [{
            "terminal_id": terminal_id,
            "capacity_per_day": master["capacity_per_day"],
            "effective_start_date": "2024-01-01",
            "effective_end_date": "",
        }]
        for version in sorted(versions, key=lambda row: row["effective_start_date"]):
            rows.append({
                "terminal_sk": len(rows) + 1,
                "terminal_id": terminal_id,
                "terminal_name": master["terminal_name"],
                "city": master["city"],
                "province": master["province"],
                "capacity_per_day": int(version["capacity_per_day"]),
                "effective_start_date": version["effective_start_date"],
                "effective_end_date": version["effective_end_date"],
                "is_current": not version["effective_end_date"],
            })
    return rows


def build_simple_dimensions(raw):
    route_rows = []
    for row in sorted(raw["routes"], key=lambda item: item["route_id"]):
        route_rows.append({
            "route_sk": len(route_rows) + 1,
            **row,
        })

    contexts = sorted({
        (
            row["booking_channel"], row["fare_class"],
            row["payment_method"], row["is_refundable"],
        )
        for row in raw["bookings"]
    })
    sales_context_rows = [
        {
            "sales_context_sk": index,
            "booking_channel": value[0],
            "fare_class": value[1],
            "payment_method": value[2],
            "is_refundable": value[3],
        }
        for index, value in enumerate(contexts, start=1)
    ]

    promotion_rows = [{
        "promotion_sk": 0,
        "promotion_code": "",
        "promotion_name": "Tanpa Promosi",
        "promotion_type": "None",
        "discount_rate": 0,
    }]
    for row in sorted(raw["promotions"], key=lambda item: item["promotion_code"]):
        promotion_rows.append({"promotion_sk": len(promotion_rows), **row})

    disruption_values = sorted({
        (row["disruption_reason"], row["severity_level"])
        for row in raw["trip_events"] if row["disruption_reason"]
    })
    disruption_rows = [{
        "disruption_reason_sk": 0,
        "disruption_reason": "",
        "severity_level": "",
    }]
    for reason, severity in disruption_values:
        disruption_rows.append({
            "disruption_reason_sk": len(disruption_rows),
            "disruption_reason": reason,
            "severity_level": severity,
        })

    loyalty_types = sorted({row["transaction_type"] for row in raw["loyalty"]})
    loyalty_type_rows = [
        {
            "loyalty_transaction_type_sk": index,
            "transaction_type": transaction_type,
        }
        for index, transaction_type in enumerate(loyalty_types, start=1)
    ]
    return route_rows, sales_context_rows, promotion_rows, disruption_rows, loyalty_type_rows


def identify_capacity_rejections(raw, fleet_dimension, fleet_lookup):
    bookings = {row["booking_id"]: row for row in raw["bookings"]}
    schedules = {row["trip_id"]: row for row in raw["schedules"]}
    claims = {row["ticket_number"]: row for row in raw["claims"]}
    fleet_by_sk = {row["bus_fleet_sk"]: row for row in fleet_dimension}
    legs_by_trip = defaultdict(list)
    for leg in raw["ticket_legs"]:
        legs_by_trip[leg["trip_id"]].append(leg)

    rejected = []
    rejected_tickets = set()
    for trip_id, legs in legs_by_trip.items():
        schedule = schedules[trip_id]
        departure = parse_timestamp(schedule["scheduled_departure_ts"])
        fleet_sk = resolve_temporal(fleet_lookup, schedule["bus_fleet_id"], departure.date())
        capacity = int(fleet_by_sk[fleet_sk]["seat_capacity"])
        ordered = sorted(legs, key=lambda row: (
            bookings[row["booking_id"]]["booking_ts"], row["ticket_number"]
        ))
        for sequence, leg in enumerate(ordered, start=1):
            if sequence <= capacity:
                continue
            rejected_tickets.add(leg["ticket_number"])
            claim = claims.get(leg["ticket_number"], {})
            rejected.append({
                "ticket_number": leg["ticket_number"],
                "booking_id": leg["booking_id"],
                "itinerary_id": leg["itinerary_id"],
                "passenger_id": leg["passenger_id"],
                "trip_id": trip_id,
                "bus_fleet_id": schedule["bus_fleet_id"],
                "scheduled_departure_ts": schedule["scheduled_departure_ts"],
                "historical_seat_capacity": capacity,
                "passenger_sequence": sequence,
                "rejection_reason": "TRIP_CAPACITY_EXCEEDED",
                "claim_id": claim.get("claim_id", ""),
                "claim_status": claim.get("claim_status", ""),
                "refund_amount": claim.get("refund_amount", 0),
                "compensation_amount": claim.get("compensation_amount", 0),
                "rebooking_cost": claim.get("rebooking_cost", 0),
            })
    return rejected_tickets, rejected


def build_facts(raw, dimensions):
    bookings = {row["booking_id"]: row for row in raw["bookings"]}
    schedules = {row["trip_id"]: row for row in raw["schedules"]}
    trip_events = {row["trip_id"]: row for row in raw["trip_events"]}
    passenger_events = {row["ticket_number"]: row for row in raw["passenger_events"]}
    claims = {row["ticket_number"]: row for row in raw["claims"]}

    passenger_lookup = build_temporal_lookup(dimensions["passenger"], "passenger_id", "passenger_sk")
    fleet_lookup = build_temporal_lookup(dimensions["fleet"], "bus_fleet_id", "bus_fleet_sk")
    terminal_lookup = build_temporal_lookup(dimensions["terminal"], "terminal_id", "terminal_sk")
    route_lookup = {row["route_id"]: row["route_sk"] for row in dimensions["route"]}
    context_lookup = {
        (
            row["booking_channel"], row["fare_class"],
            row["payment_method"], row["is_refundable"],
        ): row["sales_context_sk"]
        for row in dimensions["sales_context"]
    }
    promotion_lookup = {row["promotion_code"]: row["promotion_sk"] for row in dimensions["promotion"]}
    disruption_lookup = {
        (row["disruption_reason"], row["severity_level"]): row["disruption_reason_sk"]
        for row in dimensions["disruption"]
    }
    loyalty_type_lookup = {
        row["transaction_type"]: row["loyalty_transaction_type_sk"]
        for row in dimensions["loyalty_type"]
    }

    rejected_tickets, rejected_rows = identify_capacity_rejections(
        raw, dimensions["fleet"], fleet_lookup
    )

    ticket_sales = []
    itinerary_legs = []
    for leg in raw["ticket_legs"]:
        booking = bookings[leg["booking_id"]]
        booking_ts = parse_timestamp(booking["booking_ts"])
        schedule = schedules[leg["trip_id"]]
        trip_event = trip_events[leg["trip_id"]]
        passenger_event = passenger_events[leg["ticket_number"]]
        scheduled_departure = parse_timestamp(schedule["scheduled_departure_ts"])
        scheduled_arrival = parse_timestamp(schedule["scheduled_arrival_ts"])
        actual_departure = parse_timestamp(trip_event["actual_departure_ts"])
        actual_arrival = parse_timestamp(trip_event["actual_arrival_ts"])

        ticket_sales.append({
            "ticket_sales_sk": len(ticket_sales) + 1,
            "passenger_sk": resolve_temporal(passenger_lookup, leg["passenger_id"], booking_ts.date()),
            "booking_date_sk": date_key(booking_ts),
            "booking_time_sk": time_key(booking_ts),
            "route_sk": route_lookup[leg["route_id"]],
            "sales_context_sk": context_lookup[(
                booking["booking_channel"], booking["fare_class"],
                booking["payment_method"], booking["is_refundable"],
            )],
            "promotion_sk": promotion_lookup[leg["promotion_code"]],
            "booking_id": leg["booking_id"],
            "ticket_number": leg["ticket_number"],
            "itinerary_id": leg["itinerary_id"],
            "allocated_base_fare": leg["base_fare"],
            "discount_amount": leg["discount_amount"],
            "tax_amount": leg["tax_amount"],
            "net_ticket_revenue": leg["net_ticket_revenue"],
            "loyalty_points_earned": leg["loyalty_points_earned"],
            "loyalty_points_redeemed": leg["loyalty_points_redeemed"],
        })

        if leg["ticket_number"] in rejected_tickets:
            continue

        claim = claims.get(leg["ticket_number"], {})
        rebooking_ts = parse_timestamp(claim.get("rebooking_ts", ""))
        claim_resolution_ts = parse_timestamp(claim.get("claim_resolution_ts", ""))
        itinerary_legs.append({
            "itinerary_leg_sk": len(itinerary_legs) + 1,
            "passenger_sk": resolve_temporal(passenger_lookup, leg["passenger_id"], scheduled_departure.date()),
            "route_sk": route_lookup[leg["route_id"]],
            "bus_fleet_sk": resolve_temporal(fleet_lookup, schedule["bus_fleet_id"], scheduled_departure.date()),
            "origin_terminal_sk": resolve_temporal(terminal_lookup, leg["origin_terminal_id"], scheduled_departure.date()),
            "destination_terminal_sk": resolve_temporal(terminal_lookup, leg["destination_terminal_id"], scheduled_departure.date()),
            "disruption_reason_sk": disruption_lookup[(trip_event["disruption_reason"], trip_event["severity_level"])],
            "booking_date_sk": date_key(booking_ts),
            "booking_time_sk": time_key(booking_ts),
            "scheduled_departure_date_sk": date_key(scheduled_departure),
            "scheduled_departure_time_sk": time_key(scheduled_departure),
            "actual_departure_date_sk": date_key(actual_departure),
            "actual_departure_time_sk": time_key(actual_departure),
            "scheduled_arrival_date_sk": date_key(scheduled_arrival),
            "scheduled_arrival_time_sk": time_key(scheduled_arrival),
            "actual_arrival_date_sk": date_key(actual_arrival),
            "actual_arrival_time_sk": time_key(actual_arrival),
            "rebooking_date_sk": date_key(rebooking_ts),
            "rebooking_time_sk": time_key(rebooking_ts),
            "claim_resolution_date_sk": date_key(claim_resolution_ts),
            "claim_resolution_time_sk": time_key(claim_resolution_ts),
            "booking_id": leg["booking_id"],
            "ticket_number": leg["ticket_number"],
            "itinerary_id": leg["itinerary_id"],
            "trip_id": leg["trip_id"],
            "leg_sequence": leg["leg_sequence"],
            "total_legs": leg["total_legs"],
            "claim_id": claim.get("claim_id", ""),
            "travel_status": passenger_event["travel_status"],
            "claim_status": claim.get("claim_status", ""),
            "departure_delay_minutes": trip_event["departure_delay_minutes"],
            "arrival_delay_minutes": trip_event["arrival_delay_minutes"],
            "scheduled_connection_minutes": passenger_event["scheduled_connection_minutes"],
            "actual_connection_minutes": passenger_event["actual_connection_minutes"],
            "missed_connection_count": passenger_event["missed_connection_count"],
            "rebooking_cost": claim.get("rebooking_cost", 0),
            "refund_amount": claim.get("refund_amount", 0),
            "compensation_amount": claim.get("compensation_amount", 0),
        })

    loyalty_facts = []
    for transaction in raw["loyalty"]:
        transaction_ts = parse_timestamp(transaction["transaction_ts"])
        loyalty_facts.append({
            "loyalty_transaction_sk": len(loyalty_facts) + 1,
            "passenger_sk": resolve_temporal(passenger_lookup, transaction["passenger_id"], transaction_ts.date()),
            "transaction_date_sk": date_key(transaction_ts),
            "transaction_time_sk": time_key(transaction_ts),
            "loyalty_transaction_type_sk": loyalty_type_lookup[transaction["transaction_type"]],
            "loyalty_transaction_id": transaction["loyalty_transaction_id"],
            "reference_id": transaction["reference_id"],
            "points_transacted": transaction["points_transacted"],
            "points_balance_after": transaction["points_balance_after"],
        })

    return ticket_sales, itinerary_legs, loyalty_facts, rejected_rows


def validate_mart(dimensions, facts, rejected_rows):
    ticket_sales, itinerary_legs, loyalty_facts = facts
    if len(ticket_sales) != 25_000:
        raise ValueError("Jumlah fct_ticket_sales tidak sesuai raw_ticket_legs")
    if len(itinerary_legs) + len(rejected_rows) != 25_000:
        raise ValueError("Rekonsiliasi fact perjalanan dan karantina tidak seimbang")
    if len(rejected_rows) != 20:
        raise ValueError("Jumlah baris karantina berubah dari hasil audit")

    valid_keys = {
        "passenger_sk": {row["passenger_sk"] for row in dimensions["passenger"]},
        "route_sk": {row["route_sk"] for row in dimensions["route"]},
        "bus_fleet_sk": {row["bus_fleet_sk"] for row in dimensions["fleet"]},
        "terminal_sk": {row["terminal_sk"] for row in dimensions["terminal"]},
        "date_sk": {row["date_sk"] for row in dimensions["date"]},
        "time_sk": {row["time_sk"] for row in dimensions["time"]},
    }
    for row in ticket_sales:
        if row["passenger_sk"] not in valid_keys["passenger_sk"] or row["route_sk"] not in valid_keys["route_sk"]:
            raise ValueError("Orphan foreign key pada fct_ticket_sales")
        if row["booking_date_sk"] not in valid_keys["date_sk"] or row["booking_time_sk"] not in valid_keys["time_sk"]:
            raise ValueError("Date/time key tidak valid pada fct_ticket_sales")
    for row in itinerary_legs:
        required = (
            row["passenger_sk"] in valid_keys["passenger_sk"],
            row["route_sk"] in valid_keys["route_sk"],
            row["bus_fleet_sk"] in valid_keys["bus_fleet_sk"],
            row["origin_terminal_sk"] in valid_keys["terminal_sk"],
            row["destination_terminal_sk"] in valid_keys["terminal_sk"],
        )
        if not all(required):
            raise ValueError("Orphan foreign key pada fct_passenger_itinerary_leg")
    for row in loyalty_facts:
        if row["passenger_sk"] not in valid_keys["passenger_sk"]:
            raise ValueError("Orphan foreign key pada fct_loyalty_transaction")


def write_manifest(paths):
    files = {}
    for path in paths:
        with path.open(newline="", encoding="utf-8") as csv_file:
            row_count = sum(1 for _ in csv_file) - 1
        files[str(path.relative_to(OUTPUT_DIR))] = {
            "rows": row_count,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    manifest = {
        "source_manifest_sha256": hashlib.sha256((RAW_DIR / "manifest.json").read_bytes()).hexdigest(),
        "files": files,
        "reconciliation": {
            "raw_ticket_legs": 25_000,
            "loaded_itinerary_legs": files["facts/fct_passenger_itinerary_leg.csv"]["rows"],
            "rejected_itinerary_legs": files["rejected/rejected_itinerary_legs.csv"]["rows"],
        },
    }
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main():
    raw = {
        "passengers": read_csv("raw_passengers.csv"),
        "passenger_history": read_csv("raw_passenger_tier_history.csv"),
        "terminals": read_csv("raw_terminals.csv"),
        "terminal_history": read_csv("raw_terminal_capacity_history.csv"),
        "routes": read_csv("raw_routes.csv"),
        "fleets": read_csv("raw_bus_fleets.csv"),
        "fleet_history": read_csv("raw_bus_fleet_history.csv"),
        "schedules": read_csv("raw_bus_schedules.csv"),
        "bookings": read_csv("raw_bookings.csv"),
        "ticket_legs": read_csv("raw_ticket_legs.csv"),
        "trip_events": read_csv("raw_trip_events.csv"),
        "passenger_events": read_csv("raw_passenger_leg_events.csv"),
        "loyalty": read_csv("raw_loyalty_transactions.csv"),
        "promotions": read_csv("raw_promotions.csv"),
        "claims": read_csv("raw_compensation_claims.csv"),
    }

    timestamps = []
    timestamp_columns = {
        "bookings": ["booking_ts"],
        "schedules": ["scheduled_departure_ts", "scheduled_arrival_ts"],
        "trip_events": ["actual_departure_ts", "actual_arrival_ts"],
        "loyalty": ["transaction_ts"],
        "claims": ["rebooking_ts", "claim_submitted_ts", "claim_resolution_ts"],
    }
    for table_name, columns in timestamp_columns.items():
        for row in raw[table_name]:
            timestamps.extend(parse_timestamp(row[column]) for column in columns if row[column])

    passenger_dimension = build_passenger_dimension(raw["passengers"], raw["passenger_history"])
    fleet_dimension = build_fleet_dimension(raw["fleets"], raw["fleet_history"])
    terminal_dimension = build_terminal_dimension(raw["terminals"], raw["terminal_history"])
    route_dimension, sales_context_dimension, promotion_dimension, disruption_dimension, loyalty_type_dimension = build_simple_dimensions(raw)
    dimensions = {
        "date": build_date_dimension(timestamps),
        "time": build_time_dimension(),
        "passenger": passenger_dimension,
        "terminal": terminal_dimension,
        "route": route_dimension,
        "fleet": fleet_dimension,
        "sales_context": sales_context_dimension,
        "promotion": promotion_dimension,
        "disruption": disruption_dimension,
        "loyalty_type": loyalty_type_dimension,
    }

    ticket_sales, itinerary_legs, loyalty_facts, rejected_rows = build_facts(raw, dimensions)
    validate_mart(dimensions, (ticket_sales, itinerary_legs, loyalty_facts), rejected_rows)

    output_tables = {
        DIMENSION_DIR / "dim_date.csv": dimensions["date"],
        DIMENSION_DIR / "dim_time.csv": dimensions["time"],
        DIMENSION_DIR / "dim_passenger.csv": dimensions["passenger"],
        DIMENSION_DIR / "dim_terminal.csv": dimensions["terminal"],
        DIMENSION_DIR / "dim_route.csv": dimensions["route"],
        DIMENSION_DIR / "dim_bus_fleet.csv": dimensions["fleet"],
        DIMENSION_DIR / "dim_sales_context.csv": dimensions["sales_context"],
        DIMENSION_DIR / "dim_promotion.csv": dimensions["promotion"],
        DIMENSION_DIR / "dim_disruption_reason.csv": dimensions["disruption"],
        DIMENSION_DIR / "dim_loyalty_transaction_type.csv": dimensions["loyalty_type"],
        FACT_DIR / "fct_ticket_sales.csv": ticket_sales,
        FACT_DIR / "fct_passenger_itinerary_leg.csv": itinerary_legs,
        FACT_DIR / "fct_loyalty_transaction.csv": loyalty_facts,
        REJECTED_DIR / "rejected_itinerary_legs.csv": rejected_rows,
    }
    for path, rows in output_tables.items():
        write_csv(path, rows)
    write_manifest(list(output_tables))

    print("Data mart berhasil dibangun.")
    print(f"- fct_ticket_sales: {len(ticket_sales):,} baris")
    print(f"- fct_passenger_itinerary_leg: {len(itinerary_legs):,} baris")
    print(f"- fct_loyalty_transaction: {len(loyalty_facts):,} baris")
    print(f"- rejected_itinerary_legs: {len(rejected_rows):,} baris")
    print("Validasi foreign key dan rekonsiliasi: lulus")


if __name__ == "__main__":
    main()
