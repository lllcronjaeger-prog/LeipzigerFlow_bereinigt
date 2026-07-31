from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def _add(statements: list[str], table: str, columns: set[str], name: str, definition: str) -> None:
    if name not in columns:
        statements.append(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def migrate_database(engine: Engine) -> None:
    """Kleine kompatible Schema-Erweiterungen ohne externes Migrationswerkzeug."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    statements: list[str] = []

    if "customers" in tables:
        columns = {c["name"] for c in inspector.get_columns("customers")}
        _add(statements,"customers",columns,"disposition_priority","INTEGER NOT NULL DEFAULT 5")
        _add(statements,"customers",columns,"own_fleet_preferred","BOOLEAN NOT NULL DEFAULT 0")
        _add(statements,"customers",columns,"subcontracting_allowed","BOOLEAN NOT NULL DEFAULT 1")
        _add(statements,"customers",columns,"match_code","VARCHAR(100) NOT NULL DEFAULT ''")
        _add(statements,"customers",columns,"freight_payer_id","INTEGER")

    if "transport_orders" in tables:
        columns = {c["name"] for c in inspector.get_columns("transport_orders")}
        _add(statements,"transport_orders",columns,"customer_order_number","VARCHAR(100) NOT NULL DEFAULT ''")
        _add(statements,"transport_orders",columns,"transport_number","VARCHAR(100) NOT NULL DEFAULT ''")
        _add(statements,"transport_orders",columns,"dossier","VARCHAR(100) NOT NULL DEFAULT ''")
        _add(statements,"transport_orders",columns,"loading_reference","VARCHAR(150) NOT NULL DEFAULT ''")
        _add(statements,"transport_orders",columns,"unloading_reference","VARCHAR(150) NOT NULL DEFAULT ''")
        _add(statements,"transport_orders",columns,"order_type","VARCHAR(30) NOT NULL DEFAULT 'Transport'")
        _add(statements,"transport_orders",columns,"required_trailer_type","VARCHAR(200) NOT NULL DEFAULT 'Plane'")
        _add(statements,"transport_orders",columns,"dispatch_priority","VARCHAR(40) NOT NULL DEFAULT 'Eigenfuhrpark bevorzugt'")
        _add(statements,"transport_orders",columns,"loading_time_flexible","BOOLEAN NOT NULL DEFAULT 1")
        _add(statements,"transport_orders",columns,"loading_open_from","TIME")
        _add(statements,"transport_orders",columns,"loading_open_until","TIME")
        _add(statements,"transport_orders",columns,"unloading_time_flexible","BOOLEAN NOT NULL DEFAULT 1")
        _add(statements,"transport_orders",columns,"unloading_open_from","TIME")
        _add(statements,"transport_orders",columns,"unloading_open_until","TIME")
        _add(statements,"transport_orders",columns,"loading_original_from","TIME")
        _add(statements,"transport_orders",columns,"loading_original_until","TIME")
        _add(statements,"transport_orders",columns,"unloading_original_from","TIME")
        _add(statements,"transport_orders",columns,"unloading_original_until","TIME")
        _add(statements,"transport_orders",columns,"loading_window_status","VARCHAR(30) NOT NULL DEFAULT 'Unverändert'")
        _add(statements,"transport_orders",columns,"unloading_window_status","VARCHAR(30) NOT NULL DEFAULT 'Unverändert'")
        _add(statements,"transport_orders",columns,"loading_window_change_reason","VARCHAR(255) NOT NULL DEFAULT ''")
        _add(statements,"transport_orders",columns,"unloading_window_change_reason","VARCHAR(255) NOT NULL DEFAULT ''")
        _add(statements,"transport_orders",columns,"contractor_id","INTEGER REFERENCES contractors(id)")
        _add(statements,"transport_orders",columns,"contractor_raw","VARCHAR(255) NOT NULL DEFAULT ''")
        _add(statements,"transport_orders",columns,"assignment_type","VARCHAR(30) NOT NULL DEFAULT 'Eigener Fuhrpark'")
        _add(statements,"transport_orders",columns,"auto_dispatch_eligible","BOOLEAN NOT NULL DEFAULT 1")
        _add(statements,"transport_orders",columns,"planning_owner_hint","VARCHAR(120) NOT NULL DEFAULT ''")
        _add(statements,"transport_orders",columns,"import_rule_action","VARCHAR(50) NOT NULL DEFAULT ''")

    if "locations" in tables:
        columns = {c["name"] for c in inspector.get_columns("locations")}
        _add(statements,"locations",columns,"loading_duration_minutes","INTEGER NOT NULL DEFAULT 60")
        _add(statements,"locations",columns,"unloading_duration_minutes","INTEGER NOT NULL DEFAULT 60")
        _add(statements,"locations",columns,"time_window_booking_required","BOOLEAN NOT NULL DEFAULT 0")
        _add(statements,"locations",columns,"customer_id","INTEGER REFERENCES customers(id)")
        _add(statements,"locations",columns,"match_code","VARCHAR(100) NOT NULL DEFAULT ''")
        _add(statements,"locations",columns,"warehouse_group_id","INTEGER REFERENCES warehouse_groups(id)")
        _add(statements,"locations",columns,"use_warehouse_group_defaults","BOOLEAN NOT NULL DEFAULT 0")


    if "drivers" in tables:
        columns = {c["name"] for c in inspector.get_columns("drivers")}
        _add(statements,"drivers",columns,"match_code","VARCHAR(100) NOT NULL DEFAULT ''")
        _add(statements,"drivers",columns,"personnel_number","VARCHAR(50) NOT NULL DEFAULT ''")
        _add(statements,"drivers",columns,"modulon_driver_number","VARCHAR(50) NOT NULL DEFAULT ''")
        _add(statements,"drivers",columns,"contact_raw","VARCHAR(500) NOT NULL DEFAULT ''")
        _add(statements,"drivers",columns,"import_source","VARCHAR(100) NOT NULL DEFAULT ''")
        _add(statements,"drivers",columns,"driver_card_valid_until","DATE")
        _add(statements,"drivers",columns,"module_95_valid_until","DATE")
        _add(statements,"drivers",columns,"adr_valid_until","DATE")
        _add(statements,"drivers",columns,"absence_from","DATE")
        _add(statements,"drivers",columns,"absence_until","DATE")
        _add(statements,"drivers",columns,"absence_reason","VARCHAR(100) NOT NULL DEFAULT ''")
        _add(statements,"drivers",columns,"work_model","VARCHAR(20) NOT NULL DEFAULT 'MO-FR'")
        _add(statements,"drivers",columns,"rotation_start","DATE")
        _add(statements,"drivers",columns,"home_base","VARCHAR(100) NOT NULL DEFAULT 'Ettlingen'")
        _add(statements,"drivers",columns,"home_base_location_id","INTEGER REFERENCES locations(id)")
        _add(statements,"drivers",columns,"allowed_operation","VARCHAR(20) NOT NULL DEFAULT 'Beides'")
        _add(statements,"drivers",columns,"weekly_target_minutes","INTEGER NOT NULL DEFAULT 2880")
        _add(statements,"drivers",columns,"double_week_limit_minutes","INTEGER NOT NULL DEFAULT 5760")
        _add(statements,"drivers",columns,"dispatch_group_id","INTEGER REFERENCES dispatch_groups(id)")


    if "driver_absences" in tables:
        columns = {c["name"] for c in inspector.get_columns("driver_absences")}
        _add(statements, "driver_absences", columns, "source", "VARCHAR(100) NOT NULL DEFAULT 'Manuell'")
        _add(statements, "driver_absences", columns, "source_key", "VARCHAR(255) NOT NULL DEFAULT ''")

    if "vehicles" in tables:
        columns = {c["name"] for c in inspector.get_columns("vehicles")}
        _add(statements,"vehicles",columns,"vehicle_number","VARCHAR(30) NOT NULL DEFAULT ''")
        _add(statements,"vehicles",columns,"vehicle_class","VARCHAR(20) NOT NULL DEFAULT 'Standard'")
        _add(statements,"vehicles",columns,"ownership_type","VARCHAR(30) NOT NULL DEFAULT 'Eigenes Fahrzeug'")
        _add(statements,"vehicles",columns,"hu_date","DATE")
        _add(statements,"vehicles",columns,"location","VARCHAR(100) NOT NULL DEFAULT ''")
        _add(statements,"vehicles",columns,"status","VARCHAR(30) NOT NULL DEFAULT 'Frei'")
        _add(statements,"vehicles",columns,"remarks","TEXT NOT NULL DEFAULT ''")
        _add(statements,"vehicles",columns,"trailer_id","INTEGER REFERENCES trailers(id)")
        _add(statements,"vehicles",columns,"operation_type","VARCHAR(20) NOT NULL DEFAULT 'Nahverkehr'")
        _add(statements,"vehicles",columns,"home_base","VARCHAR(100) NOT NULL DEFAULT 'Ettlingen'")
        _add(statements,"vehicles",columns,"home_base_location_id","INTEGER REFERENCES locations(id)")
        _add(statements,"vehicles",columns,"daily_return_required","BOOLEAN NOT NULL DEFAULT 1")
        _add(statements,"vehicles",columns,"overnight_away_allowed","BOOLEAN NOT NULL DEFAULT 0")
        _add(statements,"vehicles",columns,"dispatch_group_id","INTEGER REFERENCES dispatch_groups(id)")

    if "users" in tables:
        columns = {c["name"] for c in inspector.get_columns("users")}
        _add(statements,"users",columns,"default_dispatch_group_id","INTEGER REFERENCES dispatch_groups(id)")

    if "tours" in tables:
        columns = {c["name"] for c in inspector.get_columns("tours")}
        _add(statements,"tours",columns,"planned_start_time","TIME")
        _add(statements,"tours",columns,"trailer_id","INTEGER REFERENCES trailers(id)")
        _add(statements,"tours",columns,"planning_locked","BOOLEAN NOT NULL DEFAULT 0")
        _add(statements,"tours",columns,"contractor_id","INTEGER REFERENCES contractors(id)")
        _add(statements,"tours",columns,"dispatch_group_id","INTEGER REFERENCES dispatch_groups(id)")
        _add(statements,"tours",columns,"planning_status","VARCHAR(30) NOT NULL DEFAULT 'Geplant'")
        _add(statements,"tours",columns,"priority","INTEGER NOT NULL DEFAULT 5")
        _add(statements,"tours",columns,"tour_color","VARCHAR(20) NOT NULL DEFAULT ''")

    # PR-015: Many-to-many-Zuordnungen und Gruppenregeln auch für bestehende Datenbanken.
    create_statements = [
        "CREATE TABLE IF NOT EXISTS dispatch_group_vehicles (dispatch_group_id INTEGER NOT NULL REFERENCES dispatch_groups(id) ON DELETE CASCADE, vehicle_id INTEGER NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE, PRIMARY KEY (dispatch_group_id, vehicle_id))",
        "CREATE TABLE IF NOT EXISTS dispatch_group_trailers (dispatch_group_id INTEGER NOT NULL REFERENCES dispatch_groups(id) ON DELETE CASCADE, trailer_id INTEGER NOT NULL REFERENCES trailers(id) ON DELETE CASCADE, PRIMARY KEY (dispatch_group_id, trailer_id))",
        "CREATE TABLE IF NOT EXISTS dispatch_group_drivers (dispatch_group_id INTEGER NOT NULL REFERENCES dispatch_groups(id) ON DELETE CASCADE, driver_id INTEGER NOT NULL REFERENCES drivers(id) ON DELETE CASCADE, PRIMARY KEY (dispatch_group_id, driver_id))",
        "CREATE TABLE IF NOT EXISTS dispatch_group_contractors (dispatch_group_id INTEGER NOT NULL REFERENCES dispatch_groups(id) ON DELETE CASCADE, contractor_id INTEGER NOT NULL REFERENCES contractors(id) ON DELETE CASCADE, PRIMARY KEY (dispatch_group_id, contractor_id))",
        "CREATE TABLE IF NOT EXISTS dispatch_group_rules (id INTEGER PRIMARY KEY, dispatch_group_id INTEGER NOT NULL REFERENCES dispatch_groups(id) ON DELETE CASCADE, entity_type VARCHAR(30) NOT NULL DEFAULT 'Fahrzeug', field_name VARCHAR(50) NOT NULL DEFAULT 'MatchCode', operator VARCHAR(30) NOT NULL DEFAULT 'enthält', comparison_value VARCHAR(255) NOT NULL DEFAULT '', priority INTEGER NOT NULL DEFAULT 100, active BOOLEAN NOT NULL DEFAULT 1)",
        "CREATE TABLE IF NOT EXISTS disposition_import_rules (id INTEGER PRIMARY KEY, name VARCHAR(120) NOT NULL DEFAULT '', field_name VARCHAR(50) NOT NULL DEFAULT 'Unternehmer', operator VARCHAR(30) NOT NULL DEFAULT 'ist gleich', comparison_value VARCHAR(255) NOT NULL DEFAULT '', action VARCHAR(50) NOT NULL DEFAULT 'Disposition offen', responsibility_hint VARCHAR(120) NOT NULL DEFAULT '', replacement_contractor VARCHAR(255) NOT NULL DEFAULT '', priority INTEGER NOT NULL DEFAULT 100, active BOOLEAN NOT NULL DEFAULT 1)",
        "CREATE TABLE IF NOT EXISTS tour_driver_assignments (id INTEGER PRIMARY KEY, tour_id INTEGER NOT NULL REFERENCES tours(id) ON DELETE CASCADE, driver_id INTEGER NOT NULL REFERENCES drivers(id), starts_at DATETIME NOT NULL, ends_at DATETIME NOT NULL, change_base_location_id INTEGER REFERENCES locations(id), change_base_name VARCHAR(120) NOT NULL DEFAULT '', change_reason VARCHAR(255) NOT NULL DEFAULT '', sequence INTEGER NOT NULL DEFAULT 1, created_at DATETIME NOT NULL)",
        "CREATE INDEX IF NOT EXISTS ix_tour_driver_assignments_tour_id ON tour_driver_assignments(tour_id)",
        "CREATE INDEX IF NOT EXISTS ix_tour_driver_assignments_driver_id ON tour_driver_assignments(driver_id)",
        "CREATE TABLE IF NOT EXISTS vehicle_resource_assignments (id INTEGER PRIMARY KEY, vehicle_id INTEGER NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE, driver_id INTEGER REFERENCES drivers(id), trailer_id INTEGER REFERENCES trailers(id), valid_from DATE NOT NULL, valid_until DATE, base_location_id INTEGER REFERENCES locations(id), base_name VARCHAR(120) NOT NULL DEFAULT '', reason VARCHAR(255) NOT NULL DEFAULT '', active BOOLEAN NOT NULL DEFAULT 1, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL)",
        "CREATE INDEX IF NOT EXISTS ix_vehicle_resource_assignments_vehicle_id ON vehicle_resource_assignments(vehicle_id)",
        "CREATE INDEX IF NOT EXISTS ix_vehicle_resource_assignments_driver_id ON vehicle_resource_assignments(driver_id)",
        "CREATE INDEX IF NOT EXISTS ix_vehicle_resource_assignments_validity ON vehicle_resource_assignments(valid_from, valid_until)"
    ]
    if "dispatch_groups" in tables:
        columns = {c["name"] for c in inspector.get_columns("dispatch_groups")}
        _add(statements, "dispatch_groups", columns, "is_default", "BOOLEAN NOT NULL DEFAULT 0")

    with engine.begin() as connection:
        for statement in create_statements:
            connection.execute(text(statement))
        for statement in statements:
            connection.execute(text(statement))
        refreshed=inspect(engine)
        if "locations" in refreshed.get_table_names():
            columns={c["name"] for c in refreshed.get_columns("locations")}
            if "loading_duration_minutes" in columns: connection.execute(text("UPDATE locations SET loading_duration_minutes=60 WHERE loading_duration_minutes=45"))
            if "unloading_duration_minutes" in columns: connection.execute(text("UPDATE locations SET unloading_duration_minutes=60 WHERE unloading_duration_minutes=45"))
        if "drivers" in refreshed.get_table_names() and "locations" in refreshed.get_table_names():
            columns={c["name"] for c in refreshed.get_columns("drivers")}
            if "home_base_location_id" in columns:
                connection.execute(text("""
                    UPDATE drivers
                    SET home_base_location_id = (
                        SELECT locations.id FROM locations
                        WHERE lower(locations.city) = lower(drivers.home_base)
                           OR lower(locations.name) LIKE '%' || lower(drivers.home_base) || '%'
                        ORDER BY locations.id LIMIT 1
                    )
                    WHERE home_base_location_id IS NULL
                      AND COALESCE(TRIM(home_base), '') <> ''
                """))
        if "vehicles" in refreshed.get_table_names():
            columns={c["name"] for c in refreshed.get_columns("vehicles")}
            if "vehicle_number" in columns:
                connection.execute(text("UPDATE vehicles SET vehicle_number=license_plate WHERE vehicle_number='' OR vehicle_number IS NULL"))
            if "home_base_location_id" in columns and "locations" in refreshed.get_table_names():
                connection.execute(text("""
                    UPDATE vehicles
                    SET home_base_location_id = (
                        SELECT locations.id FROM locations
                        WHERE lower(locations.city) = lower(vehicles.home_base)
                           OR lower(locations.name) LIKE '%' || lower(vehicles.home_base) || '%'
                        ORDER BY locations.id LIMIT 1
                    )
                    WHERE home_base_location_id IS NULL
                      AND COALESCE(TRIM(home_base), '') <> ''
                """))
