CREATE TABLE dim_date (
    date_sk INTEGER PRIMARY KEY,
    full_date DATE NOT NULL,
    day_of_month INTEGER NOT NULL,
    day_name VARCHAR(10) NOT NULL,
    week_of_year INTEGER NOT NULL,
    month_number INTEGER NOT NULL,
    month_name VARCHAR(10) NOT NULL,
    quarter_number INTEGER NOT NULL,
    year_number INTEGER NOT NULL,
    is_weekend BOOLEAN NOT NULL,
    is_peak_season BOOLEAN NOT NULL
);

CREATE TABLE dim_time (
    time_sk INTEGER PRIMARY KEY,
    full_time TIME NOT NULL,
    hour_number INTEGER NOT NULL,
    minute_number INTEGER NOT NULL,
    time_period VARCHAR(10) NOT NULL,
    is_peak_hour BOOLEAN NOT NULL
);

CREATE TABLE dim_passenger (
    passenger_sk INTEGER PRIMARY KEY,
    passenger_id VARCHAR(10) NOT NULL,
    passenger_name VARCHAR(100) NOT NULL,
    email VARCHAR(150),
    phone VARCHAR(30) NOT NULL,
    city VARCHAR(100) NOT NULL,
    registration_date DATE NOT NULL,
    loyalty_tier VARCHAR(20) NOT NULL,
    effective_start_date DATE NOT NULL,
    effective_end_date DATE,
    is_current BOOLEAN NOT NULL
);

CREATE TABLE dim_terminal (
    terminal_sk INTEGER PRIMARY KEY,
    terminal_id VARCHAR(10) NOT NULL,
    terminal_name VARCHAR(100) NOT NULL,
    city VARCHAR(100) NOT NULL,
    province VARCHAR(100) NOT NULL,
    capacity_per_day INTEGER NOT NULL,
    effective_start_date DATE NOT NULL,
    effective_end_date DATE,
    is_current BOOLEAN NOT NULL
);

CREATE TABLE dim_route (
    route_sk INTEGER PRIMARY KEY,
    route_id VARCHAR(10) NOT NULL,
    route_name VARCHAR(150) NOT NULL,
    origin_terminal_id VARCHAR(10) NOT NULL,
    destination_terminal_id VARCHAR(10) NOT NULL,
    distance_km INTEGER NOT NULL,
    average_travel_minutes INTEGER NOT NULL
);

CREATE TABLE dim_bus_fleet (
    bus_fleet_sk INTEGER PRIMARY KEY,
    bus_fleet_id VARCHAR(10) NOT NULL,
    license_plate VARCHAR(20) NOT NULL,
    bus_class VARCHAR(20) NOT NULL,
    seat_configuration VARCHAR(10) NOT NULL,
    seat_capacity INTEGER NOT NULL,
    manufacture_year INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL,
    effective_start_date DATE NOT NULL,
    effective_end_date DATE,
    is_current BOOLEAN NOT NULL
);

CREATE TABLE dim_sales_context (
    sales_context_sk INTEGER PRIMARY KEY,
    booking_channel VARCHAR(30) NOT NULL,
    fare_class VARCHAR(20) NOT NULL,
    payment_method VARCHAR(30) NOT NULL,
    is_refundable BOOLEAN NOT NULL
);

CREATE TABLE dim_promotion (
    promotion_sk INTEGER PRIMARY KEY,
    promotion_code VARCHAR(20),
    promotion_name VARCHAR(100) NOT NULL,
    promotion_type VARCHAR(30) NOT NULL,
    discount_rate DECIMAL(5,4) NOT NULL
);

CREATE TABLE dim_disruption_reason (
    disruption_reason_sk INTEGER PRIMARY KEY,
    disruption_reason VARCHAR(50),
    severity_level VARCHAR(20)
);

CREATE TABLE dim_loyalty_transaction_type (
    loyalty_transaction_type_sk INTEGER PRIMARY KEY,
    transaction_type VARCHAR(20) NOT NULL
);

CREATE TABLE fct_ticket_sales (
    ticket_sales_sk INTEGER PRIMARY KEY,
    passenger_sk INTEGER NOT NULL REFERENCES dim_passenger(passenger_sk),
    booking_date_sk INTEGER NOT NULL REFERENCES dim_date(date_sk),
    booking_time_sk INTEGER NOT NULL REFERENCES dim_time(time_sk),
    route_sk INTEGER NOT NULL REFERENCES dim_route(route_sk),
    sales_context_sk INTEGER NOT NULL REFERENCES dim_sales_context(sales_context_sk),
    promotion_sk INTEGER NOT NULL REFERENCES dim_promotion(promotion_sk),
    booking_id VARCHAR(20) NOT NULL,
    ticket_number VARCHAR(20) NOT NULL,
    itinerary_id VARCHAR(20) NOT NULL,
    allocated_base_fare DECIMAL(15,2) NOT NULL,
    discount_amount DECIMAL(15,2) NOT NULL,
    tax_amount DECIMAL(15,2) NOT NULL,
    net_ticket_revenue DECIMAL(15,2) NOT NULL,
    loyalty_points_earned INTEGER NOT NULL,
    loyalty_points_redeemed INTEGER NOT NULL
);

CREATE TABLE fct_passenger_itinerary_leg (
    itinerary_leg_sk INTEGER PRIMARY KEY,
    passenger_sk INTEGER NOT NULL REFERENCES dim_passenger(passenger_sk),
    route_sk INTEGER NOT NULL REFERENCES dim_route(route_sk),
    bus_fleet_sk INTEGER NOT NULL REFERENCES dim_bus_fleet(bus_fleet_sk),
    origin_terminal_sk INTEGER NOT NULL REFERENCES dim_terminal(terminal_sk),
    destination_terminal_sk INTEGER NOT NULL REFERENCES dim_terminal(terminal_sk),
    disruption_reason_sk INTEGER NOT NULL REFERENCES dim_disruption_reason(disruption_reason_sk),
    booking_date_sk INTEGER NOT NULL REFERENCES dim_date(date_sk),
    booking_time_sk INTEGER NOT NULL REFERENCES dim_time(time_sk),
    scheduled_departure_date_sk INTEGER NOT NULL REFERENCES dim_date(date_sk),
    scheduled_departure_time_sk INTEGER NOT NULL REFERENCES dim_time(time_sk),
    actual_departure_date_sk INTEGER NOT NULL REFERENCES dim_date(date_sk),
    actual_departure_time_sk INTEGER NOT NULL REFERENCES dim_time(time_sk),
    scheduled_arrival_date_sk INTEGER NOT NULL REFERENCES dim_date(date_sk),
    scheduled_arrival_time_sk INTEGER NOT NULL REFERENCES dim_time(time_sk),
    actual_arrival_date_sk INTEGER NOT NULL REFERENCES dim_date(date_sk),
    actual_arrival_time_sk INTEGER NOT NULL REFERENCES dim_time(time_sk),
    rebooking_date_sk INTEGER REFERENCES dim_date(date_sk),
    rebooking_time_sk INTEGER REFERENCES dim_time(time_sk),
    claim_resolution_date_sk INTEGER REFERENCES dim_date(date_sk),
    claim_resolution_time_sk INTEGER REFERENCES dim_time(time_sk),
    booking_id VARCHAR(20) NOT NULL,
    ticket_number VARCHAR(20) NOT NULL,
    itinerary_id VARCHAR(20) NOT NULL,
    trip_id VARCHAR(20) NOT NULL,
    leg_sequence INTEGER NOT NULL,
    total_legs INTEGER NOT NULL,
    claim_id VARCHAR(20),
    travel_status VARCHAR(40) NOT NULL,
    claim_status VARCHAR(20),
    departure_delay_minutes INTEGER NOT NULL,
    arrival_delay_minutes INTEGER NOT NULL,
    scheduled_connection_minutes INTEGER,
    actual_connection_minutes INTEGER,
    missed_connection_count INTEGER NOT NULL,
    rebooking_cost DECIMAL(15,2) NOT NULL,
    refund_amount DECIMAL(15,2) NOT NULL,
    compensation_amount DECIMAL(15,2) NOT NULL
);

CREATE TABLE fct_loyalty_transaction (
    loyalty_transaction_sk INTEGER PRIMARY KEY,
    passenger_sk INTEGER NOT NULL REFERENCES dim_passenger(passenger_sk),
    transaction_date_sk INTEGER NOT NULL REFERENCES dim_date(date_sk),
    transaction_time_sk INTEGER NOT NULL REFERENCES dim_time(time_sk),
    loyalty_transaction_type_sk INTEGER NOT NULL
        REFERENCES dim_loyalty_transaction_type(loyalty_transaction_type_sk),
    loyalty_transaction_id VARCHAR(20) NOT NULL,
    reference_id VARCHAR(20) NOT NULL,
    points_transacted INTEGER NOT NULL,
    points_balance_after INTEGER NOT NULL
);
