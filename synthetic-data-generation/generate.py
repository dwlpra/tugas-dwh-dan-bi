import csv
import hashlib
import json
import random
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from faker import Faker


SEED = 2026
TOTAL_PASSENGERS = 4_000
TOTAL_TICKET_LEGS = 25_000
OUTPUT_DIR = Path(__file__).resolve().parent / "data" / "raw"
PEAK_MONTHS = {6, 7, 12}

# Seed tetap digunakan agar hasil pembangkitan dapat diulang secara konsisten.
random.seed(SEED)
fake = Faker("id_ID")
fake.seed_instance(SEED)


def weighted_choice(values, weights):
    return random.choices(values, weights=weights, k=1)[0]


def rupiah(value):
    return round(value / 1_000) * 1_000


def next_departure_slot(value):
    """Bulatkan waktu ke slot keberangkatan enam jam berikutnya."""
    value = value.replace(minute=0, second=0, microsecond=0)
    slot_hour = ((value.hour + 5) // 6) * 6
    if slot_hour >= 24:
        return (value + timedelta(days=1)).replace(hour=0)
    return value.replace(hour=slot_hour)


def write_csv(filename, rows, fieldnames=None):
    path = OUTPUT_DIR / filename
    if fieldnames is None:
        fieldnames = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def generate_passengers():
    # Riwayat tier dipisahkan dari data pelanggan terkini untuk skenario SCD Tipe 2.
    passengers = []
    tier_history = []
    observation_start = date(2025, 1, 1)

    for number in range(1, TOTAL_PASSENGERS + 1):
        passenger_id = f"P{number:05d}"
        registration_date = observation_start - timedelta(days=random.randint(30, 730))
        initial_tier = weighted_choice(["Basic", "Gold", "Platinum"], [75, 20, 5])
        current_tier = initial_tier

        if random.random() < 0.25 and initial_tier != "Platinum":
            changed_at = observation_start + timedelta(days=random.randint(60, 300))
            current_tier = "Gold" if initial_tier == "Basic" else "Platinum"
            tier_history.extend([
                {
                    "passenger_id": passenger_id,
                    "loyalty_tier": initial_tier,
                    "effective_start_date": registration_date.isoformat(),
                    "effective_end_date": changed_at.isoformat(),
                },
                {
                    "passenger_id": passenger_id,
                    "loyalty_tier": current_tier,
                    "effective_start_date": changed_at.isoformat(),
                    "effective_end_date": "",
                },
            ])
        else:
            tier_history.append({
                "passenger_id": passenger_id,
                "loyalty_tier": initial_tier,
                "effective_start_date": registration_date.isoformat(),
                "effective_end_date": "",
            })

        passengers.append({
            "passenger_id": passenger_id,
            "passenger_name": fake.name(),
            "email": "" if random.random() < 0.015 else fake.unique.email(),
            "phone": fake.phone_number(),
            "city": fake.city_name(),
            "loyalty_tier": current_tier,
            "registration_date": registration_date.isoformat(),
        })

    return passengers, tier_history


def generate_reference_data():
    # Terminal, rute, dan armada menjadi data referensi untuk jadwal perjalanan.
    cities = [
        "Jakarta", "Bandung", "Semarang", "Yogyakarta", "Surabaya",
        "Malang", "Solo", "Cirebon", "Tegal", "Purwokerto",
        "Kediri", "Madiun", "Jember", "Probolinggo", "Banyuwangi",
        "Bogor", "Sukabumi", "Tasikmalaya", "Garut", "Cilacap",
        "Pekalongan", "Magelang", "Salatiga", "Jepara", "Pati",
    ]
    provinces = [
        "DKI Jakarta", "Jawa Barat", "Jawa Tengah", "DI Yogyakarta", "Jawa Timur",
        "Jawa Timur", "Jawa Tengah", "Jawa Barat", "Jawa Tengah", "Jawa Tengah",
        "Jawa Timur", "Jawa Timur", "Jawa Timur", "Jawa Timur", "Jawa Timur",
        "Jawa Barat", "Jawa Barat", "Jawa Barat", "Jawa Barat", "Jawa Tengah",
        "Jawa Tengah", "Jawa Tengah", "Jawa Tengah", "Jawa Tengah", "Jawa Tengah",
    ]
    terminals = [
        {
            "terminal_id": f"TRM-{index:02d}",
            "terminal_name": f"Terminal {city}",
            "city": city,
            "province": provinces[index - 1],
            "capacity_per_day": random.randrange(500, 3001, 100),
        }
        for index, city in enumerate(cities, start=1)
    ]

    route_pairs = []
    for index in range(25):
        route_pairs.append((index, (index + 1) % 25))
    route_pairs.extend([(0, 4), (4, 9), (9, 14), (14, 19), (19, 24)])

    routes = []
    for index, (origin_index, destination_index) in enumerate(route_pairs, start=1):
        distance = random.randint(90, 650)
        routes.append({
            "route_id": f"RTE-{index:02d}",
            "route_name": f"{cities[origin_index]} - {cities[destination_index]}",
            "origin_terminal_id": terminals[origin_index]["terminal_id"],
            "destination_terminal_id": terminals[destination_index]["terminal_id"],
            "distance_km": distance,
            "average_travel_minutes": round(distance / random.uniform(42, 55) * 60),
        })

    bus_classes = {
        "Economy": (40, 45),
        "Executive": (28, 36),
        "Sleeper": (18, 24),
    }
    fleets = []
    for index in range(1, 81):
        bus_class = weighted_choice(list(bus_classes), [35, 50, 15])
        minimum, maximum = bus_classes[bus_class]
        seat_capacity = random.randrange(minimum, maximum + 1, 2)
        fleets.append({
            "bus_fleet_id": f"BUS-{index:03d}",
            "license_plate": f"{random.choice(['B', 'D', 'H', 'L', 'N', 'AB'])} {random.randint(1000, 9999)} {fake.lexify('??').upper()}",
            "bus_class": bus_class,
            "seat_configuration": {
                "Economy": "2-2", "Executive": "2-2", "Sleeper": "1-1"
            }[bus_class],
            "seat_capacity": seat_capacity,
            "manufacture_year": random.randint(2014, 2025),
            "status": weighted_choice(["Active", "Maintenance"], [95, 5]),
        })

    return terminals, routes, fleets


def generate_reference_histories(terminals, fleets):
    # Sebagian armada dan terminal diberi dua versi historis untuk pengujian ETL.
    fleet_history = []
    for fleet in random.sample(fleets, 12):
        changed_at = date(2025, random.randint(4, 9), 1)
        previous_class = random.choice([value for value in ("Economy", "Executive", "Sleeper") if value != fleet["bus_class"]])
        previous_configuration = {"Economy": "2-2", "Executive": "2-2", "Sleeper": "1-1"}[previous_class]
        previous_capacity = {"Economy": 40, "Executive": 32, "Sleeper": 20}[previous_class]
        fleet_history.extend([
            {
                "bus_fleet_id": fleet["bus_fleet_id"], "bus_class": previous_class,
                "seat_configuration": previous_configuration, "seat_capacity": previous_capacity,
                "effective_start_date": "2024-01-01", "effective_end_date": changed_at.isoformat(),
            },
            {
                "bus_fleet_id": fleet["bus_fleet_id"], "bus_class": fleet["bus_class"],
                "seat_configuration": fleet["seat_configuration"], "seat_capacity": fleet["seat_capacity"],
                "effective_start_date": changed_at.isoformat(), "effective_end_date": "",
            },
        ])

    terminal_history = []
    for terminal in random.sample(terminals, 5):
        changed_at = date(2025, random.randint(4, 9), 1)
        previous_capacity = max(300, terminal["capacity_per_day"] - random.choice([200, 300, 500]))
        terminal_history.extend([
            {
                "terminal_id": terminal["terminal_id"], "capacity_per_day": previous_capacity,
                "effective_start_date": "2024-01-01", "effective_end_date": changed_at.isoformat(),
            },
            {
                "terminal_id": terminal["terminal_id"], "capacity_per_day": terminal["capacity_per_day"],
                "effective_start_date": changed_at.isoformat(), "effective_end_date": "",
            },
        ])
    return fleet_history, terminal_history


def create_route_graph(routes):
    # Graf digunakan agar tujuan suatu leg menjadi asal leg berikutnya.
    graph = defaultdict(list)
    for route in routes:
        graph[route["origin_terminal_id"]].append(route)
    return graph


def choose_route_chain(graph, length):
    possible_starts = [terminal for terminal, outgoing in graph.items() if outgoing]
    for _ in range(100):
        current = random.choice(possible_starts)
        chain = []
        for _ in range(length):
            options = graph.get(current, [])
            if not options:
                break
            route = random.choice(options)
            chain.append(route)
            current = route["destination_terminal_id"]
        if len(chain) == length:
            return chain
    raise RuntimeError("Tidak dapat membentuk perjalanan multi-leg yang terhubung")


def plan_leg_counts():
    # Kombinasi 1--3 leg disusun sampai jumlah transaksi tepat 25.000 baris.
    counts = []
    remaining = TOTAL_TICKET_LEGS
    while remaining:
        leg_count = weighted_choice([1, 2, 3], [25, 50, 25])
        if leg_count > remaining:
            leg_count = remaining
        counts.append(leg_count)
        remaining -= leg_count
    return counts


def generate_bookings_and_legs(passengers, routes, fleets):
    graph = create_route_graph(routes)
    passenger_by_id = {row["passenger_id"]: row for row in passengers}
    fleet_by_id = {row["bus_fleet_id"]: row for row in fleets}
    active_fleet_ids = [row["bus_fleet_id"] for row in fleets if row["status"] == "Active"]
    schedules_by_key = {}
    schedules = []
    schedule_loads = defaultdict(int)
    bookings = []
    ticket_legs = []

    # Tanggal layanan dibatasi agar beberapa penumpang memakai perjalanan yang sama.
    service_dates = [
        date(2025, month, day)
        for month in range(1, 13)
        for day in (8, 22)
    ]
    # Peluang perjalanan pada musim sibuk dibuat tiga kali lebih besar.
    service_date_weights = [3 if value.month in PEAK_MONTHS else 1 for value in service_dates]

    for booking_number, leg_count in enumerate(plan_leg_counts(), start=1):
        passenger_id = random.choice(list(passenger_by_id))
        travel_date = random.choices(service_dates, weights=service_date_weights, k=1)[0]
        booking_ts = datetime.combine(
            travel_date - timedelta(days=random.randint(1, 30)),
            datetime.min.time(),
        ).replace(hour=random.randint(7, 21), minute=random.randint(0, 59))
        chain = choose_route_chain(graph, leg_count)
        booking_id = f"BKG-{booking_number:06d}"
        itinerary_id = f"ITI-{booking_number:06d}"
        fare_class = weighted_choice(["Regular", "Flexi", "Promo"], [60, 25, 15])
        promotion_code = weighted_choice(["", "EARLY10", "APP5", "PEAK5"], [65, 15, 15, 5])

        for leg_sequence, route in enumerate(chain, start=1):
            if leg_sequence > 1:
                previous_schedule = schedules_by_key[ticket_legs[-1]["trip_id"]]
                previous_arrival = datetime.fromisoformat(previous_schedule["scheduled_arrival_ts"])
                scheduled_departure = next_departure_slot(previous_arrival + timedelta(minutes=30))
            else:
                scheduled_departure = datetime.combine(travel_date, datetime.min.time()).replace(
                    hour=weighted_choice([6, 12, 18], [35, 40, 25])
                )

            trip_key = (route["route_id"], scheduled_departure.strftime("%Y%m%d%H%M"))
            # Jika satu jadwal penuh, penumpang dialihkan ke slot enam jam berikutnya.
            while trip_key in schedules_by_key:
                candidate = schedules_by_key[trip_key]
                capacity = fleet_by_id[candidate["bus_fleet_id"]]["seat_capacity"]
                if schedule_loads[candidate["trip_id"]] < capacity:
                    break
                scheduled_departure += timedelta(hours=6)
                trip_key = (route["route_id"], scheduled_departure.strftime("%Y%m%d%H%M"))
            if trip_key not in schedules_by_key:
                trip_id = f"TRIP-{len(schedules) + 1:06d}"
                bus_fleet_id = random.choice(active_fleet_ids)
                scheduled_arrival = scheduled_departure + timedelta(minutes=route["average_travel_minutes"])
                schedule = {
                    "trip_id": trip_id,
                    "route_id": route["route_id"],
                    "bus_fleet_id": bus_fleet_id,
                    "scheduled_departure_ts": scheduled_departure.isoformat(sep=" "),
                    "scheduled_arrival_ts": scheduled_arrival.isoformat(sep=" "),
                }
                schedules_by_key[trip_key] = schedule
                schedules_by_key[trip_id] = schedule
                schedules.append(schedule)
            schedule = schedules_by_key[trip_key]
            schedule_loads[schedule["trip_id"]] += 1
            fleet = fleet_by_id[schedule["bus_fleet_id"]]
            peak_multiplier = 1.20 if travel_date.month in PEAK_MONTHS else 1.0
            class_multiplier = {"Economy": 0.8, "Executive": 1.0, "Sleeper": 1.35}[fleet["bus_class"]]
            base_fare = rupiah(route["distance_km"] * 550 * class_multiplier * peak_multiplier)
            discount_rate = {"": 0, "EARLY10": 0.10, "APP5": 0.05, "PEAK5": 0.05}[promotion_code]
            discount = rupiah(base_fare * discount_rate)
            tax = rupiah((base_fare - discount) * 0.11)
            net_revenue = base_fare - discount + tax

            ticket_legs.append({
                "ticket_number": f"TICK-{len(ticket_legs) + 1:06d}",
                "booking_id": booking_id,
                "itinerary_id": itinerary_id,
                "passenger_id": passenger_id,
                "leg_sequence": leg_sequence,
                "total_legs": leg_count,
                "trip_id": schedule["trip_id"],
                "route_id": route["route_id"],
                "origin_terminal_id": route["origin_terminal_id"],
                "destination_terminal_id": route["destination_terminal_id"],
                "base_fare": base_fare,
                "discount_amount": discount,
                "tax_amount": tax,
                "net_ticket_revenue": net_revenue,
                "loyalty_points_earned": max(1, round(net_revenue / 10_000)),
                "loyalty_points_redeemed": 0,
                "promotion_code": promotion_code,
            })

        bookings.append({
            "booking_id": booking_id,
            "itinerary_id": itinerary_id,
            "passenger_id": passenger_id,
            "booking_ts": booking_ts.isoformat(sep=" "),
            "booking_channel": weighted_choice(["Mobile App", "Website", "Agent", "Counter"], [45, 30, 15, 10]),
            "fare_class": fare_class,
            "payment_method": weighted_choice(["Bank Transfer", "E-Wallet", "Card", "Cash"], [35, 35, 20, 10]),
            "is_refundable": fare_class != "Promo",
            "total_legs": leg_count,
        })

    return bookings, ticket_legs, schedules


def generate_operations(ticket_legs, schedules):
    # Keterlambatan dibuat sekali per trip agar sama bagi seluruh penumpang bus tersebut.
    trip_events = []
    event_by_trip = {}
    for schedule in schedules:
        scheduled_departure = datetime.fromisoformat(schedule["scheduled_departure_ts"])
        scheduled_arrival = datetime.fromisoformat(schedule["scheduled_arrival_ts"])
        departure_delay = max(0, round(random.gauss(10, 18)))
        arrival_delay = max(0, round(departure_delay + random.gauss(5, 20)))
        disruption_reason = ""
        severity_level = ""
        if random.random() < 0.03:
            # Sekitar tiga persen trip diberi gangguan dengan keterlambatan ekstrem.
            arrival_delay = random.randint(120, 300)
            disruption_reason = weighted_choice(["Kerusakan Mesin", "Kemacetan", "Cuaca"], [50, 30, 20])
            severity_level = "High" if arrival_delay >= 180 else "Medium"
        event = {
            "trip_id": schedule["trip_id"],
            "actual_departure_ts": (scheduled_departure + timedelta(minutes=departure_delay)).isoformat(sep=" "),
            "actual_arrival_ts": (scheduled_arrival + timedelta(minutes=arrival_delay)).isoformat(sep=" "),
            "departure_delay_minutes": departure_delay,
            "arrival_delay_minutes": arrival_delay,
            "disruption_reason": disruption_reason,
            "severity_level": severity_level,
        }
        trip_events.append(event)
        event_by_trip[event["trip_id"]] = event

    schedule_by_trip = {row["trip_id"]: row for row in schedules}
    itineraries = defaultdict(list)
    for leg in ticket_legs:
        itineraries[leg["itinerary_id"]].append(leg)

    passenger_events = []
    claims = []
    for legs in itineraries.values():
        legs.sort(key=lambda row: row["leg_sequence"])
        disrupted = False
        for index, leg in enumerate(legs):
            missed = 0
            status = "COMPLETED"
            scheduled_connection = ""
            actual_connection = ""
            if disrupted:
                status = "CANCELLED_AFTER_DISRUPTION"
            elif index > 0:
                previous = legs[index - 1]
                previous_actual_arrival = datetime.fromisoformat(event_by_trip[previous["trip_id"]]["actual_arrival_ts"])
                current_departure = datetime.fromisoformat(schedule_by_trip[leg["trip_id"]]["scheduled_departure_ts"])
                current_actual_departure = datetime.fromisoformat(event_by_trip[leg["trip_id"]]["actual_departure_ts"])
                previous_scheduled_arrival = datetime.fromisoformat(schedule_by_trip[previous["trip_id"]]["scheduled_arrival_ts"])
                scheduled_connection = round((current_departure - previous_scheduled_arrival).total_seconds() / 60)
                actual_connection = round((current_actual_departure - previous_actual_arrival).total_seconds() / 60)
                if actual_connection < 15:
                    # Penumpang dianggap gagal tersambung jika sisa waktu kurang dari 15 menit.
                    missed = 1
                    disrupted = True
                    status = "MISSED_CONNECTION"
                    refund = rupiah(float(leg["net_ticket_revenue"]) * 0.5)
                    compensation = weighted_choice([50_000, 75_000, 100_000], [40, 45, 15])
                    claim_submitted = previous_actual_arrival + timedelta(hours=random.randint(1, 12))
                    claim_status = weighted_choice(["Approved", "Pending", "Rejected"], [85, 10, 5])
                    claims.append({
                        "claim_id": f"CLM-{len(claims) + 1:06d}",
                        "ticket_number": leg["ticket_number"],
                        "claim_type": "Missed Connection",
                        "refund_amount": refund,
                        "compensation_amount": compensation,
                        "rebooking_cost": rupiah(float(leg["base_fare"]) * 0.35),
                        "rebooking_ts": (claim_submitted + timedelta(hours=random.randint(1, 8))).isoformat(sep=" "),
                        "claim_submitted_ts": claim_submitted.isoformat(sep=" "),
                        "claim_resolution_ts": "" if claim_status == "Pending" else (
                            claim_submitted + timedelta(days=random.randint(1, 5))
                        ).isoformat(sep=" "),
                        "claim_status": claim_status,
                    })

            scheduled_departure = datetime.fromisoformat(schedule_by_trip[leg["trip_id"]]["scheduled_departure_ts"])
            passenger_events.append({
                "ticket_number": leg["ticket_number"],
                "passenger_id": leg["passenger_id"],
                "trip_id": leg["trip_id"],
                "travel_status": status,
                "check_in_ts": "" if status != "COMPLETED" else (
                    scheduled_departure - timedelta(minutes=random.randint(35, 90))
                ).isoformat(sep=" "),
                "boarding_ts": "" if status != "COMPLETED" else (
                    scheduled_departure - timedelta(minutes=random.randint(10, 30))
                ).isoformat(sep=" "),
                "scheduled_connection_minutes": scheduled_connection,
                "actual_connection_minutes": actual_connection,
                "missed_connection_count": missed,
            })

    return trip_events, passenger_events, claims


def generate_loyalty_transactions(bookings, ticket_legs):
    # Saldo dihitung sebagai ledger: EARN menambah dan REDEEM mengurangi poin.
    legs_by_booking = defaultdict(list)
    for leg in ticket_legs:
        legs_by_booking[leg["booking_id"]].append(leg)

    events_by_passenger = defaultdict(list)
    for booking in bookings:
        revenue = sum(float(leg["net_ticket_revenue"]) for leg in legs_by_booking[booking["booking_id"]])
        points = max(1, round(revenue / 10_000))
        events_by_passenger[booking["passenger_id"]].append({
            "transaction_date": datetime.fromisoformat(booking["booking_ts"]).date().isoformat(),
            "transaction_type": "EARN",
            "points": points,
            "reference_id": booking["booking_id"],
        })
        if random.random() < 0.12:
            events_by_passenger[booking["passenger_id"]].append({
                "transaction_date": datetime.fromisoformat(booking["booking_ts"]).date().isoformat(),
                "transaction_type": "REDEEM",
                "points": -random.choice([10, 20, 30]),
                "reference_id": booking["booking_id"],
            })

    transactions = []
    for passenger_id, events in events_by_passenger.items():
        balance = 0
        events.sort(key=lambda row: (row["transaction_date"], row["transaction_type"] != "EARN"))
        for event in events:
            points = event["points"]
            if balance + points < 0:
                continue
            balance += points
            if event["transaction_type"] == "REDEEM":
                legs_by_booking[event["reference_id"]][0]["loyalty_points_redeemed"] += abs(points)
            transactions.append({
                "loyalty_transaction_id": f"LTX-{len(transactions) + 1:07d}",
                "passenger_id": passenger_id,
                "transaction_ts": (
                    f"{event['transaction_date']} 09:00:00"
                    if event["transaction_type"] == "EARN"
                    else f"{event['transaction_date']} 18:00:00"
                ),
                "transaction_type": event["transaction_type"],
                "points_transacted": points,
                "points_balance_after": balance,
                "reference_id": event["reference_id"],
            })
    return transactions


def validate(passengers, terminals, routes, fleets, bookings, ticket_legs, schedules, passenger_events, loyalty_transactions):
    # Validasi dihentikan segera jika ditemukan relasi atau aturan bisnis yang salah.
    passenger_ids = {row["passenger_id"] for row in passengers}
    terminal_ids = {row["terminal_id"] for row in terminals}
    route_ids = {row["route_id"] for row in routes}
    fleet_ids = {row["bus_fleet_id"] for row in fleets}
    booking_ids = {row["booking_id"] for row in bookings}
    trip_ids = {row["trip_id"] for row in schedules}
    ticket_numbers = {row["ticket_number"] for row in ticket_legs}

    assert len(ticket_legs) == TOTAL_TICKET_LEGS
    assert all(row["passenger_id"] in passenger_ids for row in bookings)
    assert all(row["booking_id"] in booking_ids and row["route_id"] in route_ids for row in ticket_legs)
    assert all(row["trip_id"] in trip_ids and row["passenger_id"] in passenger_ids for row in ticket_legs)
    assert all(row["origin_terminal_id"] in terminal_ids and row["destination_terminal_id"] in terminal_ids for row in ticket_legs)
    assert all(row["bus_fleet_id"] in fleet_ids for row in schedules)
    assert all(row["ticket_number"] in ticket_numbers for row in passenger_events)
    assert all(row["points_balance_after"] >= 0 for row in loyalty_transactions)

    fleet_by_id = {row["bus_fleet_id"]: row for row in fleets}
    schedule_by_trip = {row["trip_id"]: row for row in schedules}
    passengers_per_trip = defaultdict(int)
    for row in ticket_legs:
        passengers_per_trip[row["trip_id"]] += 1
    assert all(
        count <= fleet_by_id[schedule_by_trip[trip_id]["bus_fleet_id"]]["seat_capacity"]
        for trip_id, count in passengers_per_trip.items()
    )

    passenger_by_id = {row["passenger_id"]: row for row in passengers}
    assert all(
        datetime.fromisoformat(row["booking_ts"]).date() >= date.fromisoformat(passenger_by_id[row["passenger_id"]]["registration_date"])
        for row in bookings
    )

    itineraries = defaultdict(list)
    for leg in ticket_legs:
        itineraries[leg["itinerary_id"]].append(leg)
    for legs in itineraries.values():
        legs.sort(key=lambda row: row["leg_sequence"])
        assert all(legs[index - 1]["destination_terminal_id"] == legs[index]["origin_terminal_id"] for index in range(1, len(legs)))


def create_manifest(paths, row_counts):
    # Checksum membantu mendeteksi perubahan pada CSV setelah data dibangkitkan.
    files = {}
    for path in paths:
        files[path.name] = {
            "rows": row_counts[path.name],
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    manifest = {
        "seed": SEED,
        "generated_at": "deterministic; timestamps are part of the synthetic records",
        "files": files,
    }
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main():
    # Raw data tidak ditimpa jika direktori tujuan sudah berisi file.
    if OUTPUT_DIR.exists() and any(OUTPUT_DIR.iterdir()):
        print(f"Data mentah sudah tersedia di: {OUTPUT_DIR}")
        print("Proses generate dilewati agar file yang ada tidak tertimpa.")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    passengers, tier_history = generate_passengers()
    terminals, routes, fleets = generate_reference_data()
    fleet_history, terminal_history = generate_reference_histories(terminals, fleets)
    bookings, ticket_legs, schedules = generate_bookings_and_legs(passengers, routes, fleets)
    trip_events, passenger_events, claims = generate_operations(ticket_legs, schedules)
    loyalty_transactions = generate_loyalty_transactions(bookings, ticket_legs)

    promotions = [
        {"promotion_code": "EARLY10", "promotion_name": "Pemesanan Awal", "promotion_type": "Percentage", "discount_rate": 0.10},
        {"promotion_code": "APP5", "promotion_name": "Pemesanan Aplikasi", "promotion_type": "Percentage", "discount_rate": 0.05},
        {"promotion_code": "PEAK5", "promotion_name": "Promo Musim Sibuk", "promotion_type": "Percentage", "discount_rate": 0.05},
    ]

    validate(passengers, terminals, routes, fleets, bookings, ticket_legs, schedules, passenger_events, loyalty_transactions)

    datasets = {
        "raw_passengers.csv": passengers,
        "raw_passenger_tier_history.csv": tier_history,
        "raw_terminals.csv": terminals,
        "raw_routes.csv": routes,
        "raw_bus_fleets.csv": fleets,
        "raw_bus_fleet_history.csv": fleet_history,
        "raw_terminal_capacity_history.csv": terminal_history,
        "raw_bus_schedules.csv": schedules,
        "raw_bookings.csv": bookings,
        "raw_ticket_legs.csv": ticket_legs,
        "raw_trip_events.csv": trip_events,
        "raw_passenger_leg_events.csv": passenger_events,
        "raw_loyalty_transactions.csv": loyalty_transactions,
        "raw_promotions.csv": promotions,
    }
    paths = [write_csv(filename, rows) for filename, rows in datasets.items()]
    claim_fields = ["claim_id", "ticket_number", "claim_type", "refund_amount", "compensation_amount", "rebooking_cost", "rebooking_ts", "claim_submitted_ts", "claim_resolution_ts", "claim_status"]
    paths.append(write_csv("raw_compensation_claims.csv", claims, claim_fields))
    row_counts = {filename: len(rows) for filename, rows in datasets.items()}
    row_counts["raw_compensation_claims.csv"] = len(claims)
    create_manifest(paths, row_counts)

    print(f"Data mentah tersimpan di: {OUTPUT_DIR}")
    for filename, count in row_counts.items():
        print(f"- {filename}: {count:,} baris")
    print("Validasi relasi, urutan waktu, dan saldo loyalitas: lulus")


if __name__ == "__main__":
    main()
