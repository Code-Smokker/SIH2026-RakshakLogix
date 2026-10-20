"""
RakshakLogix — Synthetic Logistics Data Generator

Generates realistic, deterministic synthetic datasets for forward logistics:
- 50 synthetic locations (Depots, Hubs, Forward Posts)
- 20 supply categories/items
- 180 days historical consumption time series
- 30 vehicles
- 100+ synthetic route segments
- 180 days weather observations
- 10,000+ inventory transactions
- 1,000+ synthetic shipments

Uses a deterministic seed (default: 42) for reproducible data generation.
"""

from __future__ import annotations

import random
import uuid
from datetime import UTC, date, datetime, timedelta

from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.models.consumption import ConsumptionRecord
from app.models.inventory import Inventory, InventoryTransaction, TransactionType
from app.models.item import Item, ItemCategory, ItemCriticality, ItemUnit
from app.models.location import Location, LocationStatus, LocationType, TerrainType
from app.models.route import Route, RouteSegment, RouteStatus
from app.models.shipment import Shipment, ShipmentItem, ShipmentPriority, ShipmentStatus
from app.models.user import User, UserRole, UserStatus
from app.models.vehicle import Vehicle, VehicleStatus, VehicleType
from app.models.weather import WeatherRecord, WeatherSeverity


def _point(longitude: float, latitude: float) -> WKTElement:
    """PostGIS POINT in longitude, latitude order (SRID 4326)."""
    return WKTElement(f"POINT({longitude} {latitude})", srid=4326)


class SyntheticDataGenerator:
    """Orchestrates deterministic synthetic data generation."""

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed

    def set_seed(self) -> None:
        random.seed(self.seed)

    async def generate_all(self, db: AsyncSession) -> dict[str, int]:
        self.set_seed()

        # Check existing data
        res = await db.execute(select(User).where(User.email == "admin@rakshaklogix.dev"))
        if res.scalar_one_or_none():
            return {"status": 0, "message": "Database already seeded."}

        counts: dict[str, int] = {}

        # 1. Users
        users = [
            User(
                name="Command Admin",
                email="admin@rakshaklogix.dev",
                password_hash=hash_password("Admin@123456"),
                role=UserRole.ADMIN.value,
                status=UserStatus.ACTIVE.value,
            ),
            User(
                name="Major V. Sharma (Logistics Planner)",
                email="planner@rakshaklogix.dev",
                password_hash=hash_password("Planner@123456"),
                role=UserRole.LOGISTICS_PLANNER.value,
                status=UserStatus.ACTIVE.value,
            ),
            User(
                name="Captain A. Kumar (Transport Coordinator)",
                email="transport@rakshaklogix.dev",
                password_hash=hash_password("Transport@123456"),
                role=UserRole.TRANSPORT_COORDINATOR.value,
                status=UserStatus.ACTIVE.value,
            ),
            User(
                name="Brigadier S. Singh (Command Viewer)",
                email="command@rakshaklogix.dev",
                password_hash=hash_password("Command@123456"),
                role=UserRole.COMMAND_VIEWER.value,
                status=UserStatus.ACTIVE.value,
            ),
            User(
                name="Dr. R. Verma (Data & ML Analyst)",
                email="analyst@rakshaklogix.dev",
                password_hash=hash_password("Analyst@123456"),
                role=UserRole.DATA_ML_ANALYST.value,
                status=UserStatus.ACTIVE.value,
            ),
        ]
        db.add_all(users)
        await db.flush()
        counts["users"] = len(users)

        # 2. Locations — public geography of Jammu and Kashmir.
        # Quantities stay synthetic. Coordinates are real town centres.
        base_locations = [
            ("Jammu Satwari Supply Depot", LocationType.DEPOT, 32.7266, 74.8570, 327.0, TerrainType.PLAINS),
            ("Udhampur Northern Command Depot", LocationType.DEPOT, 32.9150, 75.1419, 755.0, TerrainType.MOUNTAIN),
            ("Akhnoor Forward Depot", LocationType.DEPOT, 32.8980, 74.7350, 310.0, TerrainType.PLAINS),
            ("Samba Distribution Hub", LocationType.HUB, 32.5623, 75.1197, 384.0, TerrainType.PLAINS),
            ("Kathua Railhead Depot", LocationType.DEPOT, 32.3860, 75.5170, 393.0, TerrainType.PLAINS),
            ("Katra Staging Hub", LocationType.HUB, 32.9916, 74.9318, 875.0, TerrainType.MOUNTAIN),
            ("Reasi Feeder Hub", LocationType.HUB, 33.0810, 74.8360, 720.0, TerrainType.MOUNTAIN),
            ("Rajouri Brigade Hub", LocationType.HUB, 33.3766, 74.3090, 915.0, TerrainType.MOUNTAIN),
            ("Nowshera Staging Post", LocationType.FORWARD_POST, 33.1550, 74.2400, 620.0, TerrainType.MOUNTAIN),
            ("Poonch Forward Post", LocationType.FORWARD_POST, 33.7670, 74.0925, 1070.0, TerrainType.MOUNTAIN),
            ("Banihal Tunnel Hub", LocationType.HUB, 33.4160, 75.1960, 1640.0, TerrainType.MOUNTAIN),
            ("Qazigund Logistics Hub", LocationType.HUB, 33.6380, 75.1580, 1670.0, TerrainType.VALLEY),
            ("Srinagar Divisional Logistics Hub", LocationType.HUB, 34.0837, 74.7973, 1585.0, TerrainType.VALLEY),
            ("Anantnag Depot", LocationType.DEPOT, 33.7311, 75.1487, 1600.0, TerrainType.VALLEY),
            ("Baramulla Forward Hub", LocationType.HUB, 34.1980, 74.3436, 1593.0, TerrainType.VALLEY),
            ("Uri Forward Post", LocationType.FORWARD_POST, 34.0870, 74.0500, 1360.0, TerrainType.MOUNTAIN),
            ("Kupwara Forward Post", LocationType.FORWARD_POST, 34.5310, 74.2660, 1811.0, TerrainType.MOUNTAIN),
            ("Gulmarg High Post", LocationType.FORWARD_POST, 34.0484, 74.3805, 2650.0, TerrainType.MOUNTAIN),
            ("Pahalgam High Post", LocationType.FORWARD_POST, 34.0161, 75.3150, 2740.0, TerrainType.MOUNTAIN),
            ("Sonamarg High Post", LocationType.FORWARD_POST, 34.3030, 75.2910, 2740.0, TerrainType.MOUNTAIN),
        ]

        loc_objects = []
        for name, ltype, lat, lon, elev, terr in base_locations:
            loc = Location(
                name=name,
                type=ltype.value,
                latitude=lat,
                longitude=lon,
                elevation_m=elev,
                terrain_type=terr.value,
                capacity=round(random.uniform(1000.0, 10000.0), 1),
                priority=random.randint(1, 10),
                status=LocationStatus.ACTIVE.value,
                geom=_point(lon, lat),
            )
            loc_objects.append(loc)

        valley_posts = [
            ("Kishtwar Feeder Post", 33.3116, 75.7662, 1638.0),
            ("Doda Staging Post", 33.1457, 75.5476, 1107.0),
            ("Bhaderwah Forward Post", 32.9800, 75.7130, 1613.0),
            ("Ramban Highway Post", 33.2420, 75.2390, 1156.0),
            ("Batote Relay Post", 33.1180, 75.3150, 1560.0),
            ("Chenani Depot Spur", 33.0390, 75.2870, 1100.0),
            ("Ramnagar Outpost", 32.8070, 75.3110, 850.0),
            ("Billawar Feeder", 32.6140, 75.6160, 760.0),
            ("Basohli River Post", 32.5080, 75.8140, 460.0),
            ("Hiranagar Rail Spur", 32.4550, 75.2720, 340.0),
            ("Awantipora Logistics Post", 33.9200, 75.0150, 1600.0),
            ("Pulwama Distribution Post", 33.8740, 74.8990, 1630.0),
            ("Shopian Hub Post", 33.7160, 74.8310, 2057.0),
            ("Kulgam Forward Post", 33.6450, 75.0180, 1739.0),
            ("Bijbehara Staging Post", 33.7930, 75.1070, 1595.0),
            ("Tral Valley Post", 33.9310, 75.1160, 1662.0),
            ("Pampore Depot Spur", 34.0130, 74.9310, 1575.0),
            ("Ganderbal Feeder", 34.2260, 74.7740, 1619.0),
            ("Sumbal Lake Post", 34.2300, 74.6400, 1580.0),
            ("Bandipora Forward Post", 34.4190, 74.6430, 1578.0),
            ("Sopore Market Hub", 34.2980, 74.4700, 1582.0),
            ("Handwara Forward Post", 34.4000, 74.2800, 1590.0),
            ("Tangdhar High Post", 34.5600, 73.8500, 1900.0),
            ("Karnah Ridge Post", 34.4800, 73.8300, 2100.0),
            ("Boniyar Road Post", 34.1400, 74.1900, 1450.0),
            ("Beerwah Valley Post", 34.0200, 74.5900, 1600.0),
            ("Magam Junction Post", 34.0900, 74.5900, 1580.0),
            ("Budgam Depot Spur", 33.8900, 74.6300, 1610.0),
            ("Charar-i-Sharief Post", 33.8600, 74.7700, 1930.0),
            ("Yusmarg High Post", 33.8400, 74.6700, 2396.0),
        ]
        for name, lat, lon, elev in valley_posts:
            loc = Location(
                name=name,
                type=LocationType.FORWARD_POST.value,
                latitude=lat,
                longitude=lon,
                elevation_m=elev,
                terrain_type=TerrainType.MOUNTAIN.value,
                capacity=800.0,
                priority=random.randint(3, 9),
                status=LocationStatus.ACTIVE.value,
                geom=_point(lon, lat),
            )
            loc_objects.append(loc)

        db.add_all(loc_objects)
        await db.flush()
        counts["locations"] = len(loc_objects)

        # 3. Items (20 Categories)
        item_definitions = [
            (
                "Winter Grade Diesel Fuel (5-D)",
                ItemCategory.FUEL,
                ItemUnit.LITRE,
                ItemCriticality.CRITICAL,
                730,
                10000.0,
                3000.0,
            ),
            (
                "Aviation Turbine Fuel (ATF)",
                ItemCategory.FUEL,
                ItemUnit.LITRE,
                ItemCriticality.CRITICAL,
                730,
                8000.0,
                2500.0,
            ),
            (
                "High Altitude Operational Rations (HAOR)",
                ItemCategory.FOOD,
                ItemUnit.RATION_PACK,
                ItemCriticality.HIGH,
                365,
                5000.0,
                1500.0,
            ),
            (
                "Fresh Produce & Dry Rations",
                ItemCategory.FOOD,
                ItemUnit.KG,
                ItemCriticality.MEDIUM,
                30,
                2000.0,
                500.0,
            ),
            (
                "High Altitude Trauma & Oxygen Kits",
                ItemCategory.MEDICAL,
                ItemUnit.BOX,
                ItemCriticality.CRITICAL,
                500,
                500.0,
                200.0,
            ),
            (
                "Essential Medical Supplies & Antidotes",
                ItemCategory.MEDICAL,
                ItemUnit.BOX,
                ItemCriticality.HIGH,
                365,
                400.0,
                150.0,
            ),
            (
                "7.62mm Rifle Ammunition Crate",
                ItemCategory.AMMUNITION,
                ItemUnit.BOX,
                ItemCriticality.CRITICAL,
                1825,
                1000.0,
                400.0,
            ),
            (
                "155mm Artillery Shells",
                ItemCategory.AMMUNITION,
                ItemUnit.UNIT,
                ItemCriticality.CRITICAL,
                3650,
                600.0,
                200.0,
            ),
            (
                "Extreme Cold Weather Clothing (ECWCS)",
                ItemCategory.CLOTHING,
                ItemUnit.SET,
                ItemCriticality.HIGH,
                1095,
                800.0,
                300.0,
            ),
            (
                "High Altitude Sleeping Bags (-40C)",
                ItemCategory.CLOTHING,
                ItemUnit.UNIT,
                ItemCriticality.HIGH,
                1095,
                600.0,
                200.0,
            ),
            (
                "Heavy Vehicle Engine Spare Parts",
                ItemCategory.SPARE_PARTS,
                ItemUnit.SET,
                ItemCriticality.MEDIUM,
                1825,
                200.0,
                50.0,
            ),
            (
                "Tyres & Snow Chains (4x4 / 6x6)",
                ItemCategory.SPARE_PARTS,
                ItemUnit.UNIT,
                ItemCriticality.HIGH,
                1095,
                300.0,
                100.0,
            ),
            (
                "Tactical VHF/UHF Radio Units",
                ItemCategory.COMMUNICATION,
                ItemUnit.UNIT,
                ItemCriticality.HIGH,
                1825,
                150.0,
                50.0,
            ),
            (
                "Satellite Phone Battery Packs",
                ItemCategory.COMMUNICATION,
                ItemUnit.UNIT,
                ItemCriticality.HIGH,
                730,
                400.0,
                100.0,
            ),
            (
                "Portable Diesel Generator Sets 15kVA",
                ItemCategory.EQUIPMENT,
                ItemUnit.UNIT,
                ItemCriticality.HIGH,
                1825,
                50.0,
                15.0,
            ),
            (
                "Snow Clearance & Shovel Equipment",
                ItemCategory.EQUIPMENT,
                ItemUnit.SET,
                ItemCriticality.MEDIUM,
                1825,
                300.0,
                100.0,
            ),
            (
                "Bunkers Reinforcement Cement & Steel",
                ItemCategory.CONSTRUCTION,
                ItemUnit.KG,
                ItemCriticality.LOW,
                1825,
                10000.0,
                2000.0,
            ),
            (
                "Corrugated Galvanized Iron Sheets",
                ItemCategory.CONSTRUCTION,
                ItemUnit.UNIT,
                ItemCriticality.LOW,
                1825,
                1000.0,
                200.0,
            ),
            (
                "Water Purification Powder Bags",
                ItemCategory.WATER,
                ItemUnit.BOX,
                ItemCriticality.CRITICAL,
                730,
                500.0,
                150.0,
            ),
            (
                "Kerosene Heating Fuel (SKO)",
                ItemCategory.FUEL,
                ItemUnit.LITRE,
                ItemCriticality.CRITICAL,
                730,
                12000.0,
                4000.0,
            ),
        ]

        item_objects = []
        for name, cat, unit, crit, shelf, min_s, safe_s in item_definitions:
            item = Item(
                name=name,
                category=cat.value,
                unit=unit.value,
                criticality=crit.value,
                shelf_life_days=shelf,
                min_stock=min_s,
                safety_stock=safe_s,
            )
            item_objects.append(item)

        db.add_all(item_objects)
        await db.flush()
        counts["items"] = len(item_objects)

        # 4. Vehicles (30 Vehicles)
        v_types = [
            VehicleType.LIGHT_TRUCK,
            VehicleType.MEDIUM_TRUCK,
            VehicleType.HEAVY_TRUCK,
            VehicleType.ALL_TERRAIN_VEHICLE,
            VehicleType.CONVOY,
            VehicleType.HELICOPTER,
        ]
        veh_objects = []
        for i in range(1, 31):
            vtype = v_types[i % len(v_types)]
            v = Vehicle(
                name=f"Supply Transport Vehicle-{i:02d}",
                vehicle_type=vtype.value,
                capacity_kg=(
                    15000.0
                    if vtype == VehicleType.HEAVY_TRUCK
                    else 5000.0
                    if vtype == VehicleType.MEDIUM_TRUCK
                    else 2500.0
                ),
                availability_status=(
                    VehicleStatus.AVAILABLE.value if i % 5 != 0 else VehicleStatus.IN_TRANSIT.value
                ),
                home_location_id=loc_objects[i % len(loc_objects)].id,
            )
            veh_objects.append(v)

        db.add_all(veh_objects)
        await db.flush()
        counts["vehicles"] = len(veh_objects)

        # 5. Inventory & Historical Consumption Records (180 Days)
        today = date.today()
        start_history_date = today - timedelta(days=180)

        n_consumption_records = 0
        n_transactions = 0

        for loc_idx, loc in enumerate(loc_objects[:25]):
            for item_idx, item in enumerate(item_objects[:15]):
                # Demonstrate Scenarios:
                # Scenario A: Demand Spike for location 0, item 0
                # Scenario B: Low Initial Inventory for location 1, item 0
                if loc_idx == 1 and item_idx == 0:
                    init_qty = round(item.safety_stock * 0.4, 1)  # Low stock breach scenario
                else:
                    init_qty = round(
                        random.uniform(item.safety_stock * 1.5, item.safety_stock * 3.5),
                        1,
                    )

                inv = Inventory(
                    location_id=loc.id,
                    item_id=item.id,
                    quantity=init_qty,
                    reserved_quantity=round(random.uniform(0.0, init_qty * 0.15), 1),
                    safety_stock=item.safety_stock,
                )
                db.add(inv)

                # Initial receipt transaction
                tx_init = InventoryTransaction(
                    location_id=loc.id,
                    item_id=item.id,
                    transaction_type=TransactionType.RECEIPT.value,
                    quantity=init_qty,
                    reference_id="INIT_STOCK_SEED",
                    notes="Initial seed receipt",
                    performed_by_id=users[0].id,
                )
                db.add(tx_init)
                n_transactions += 1

                # Generate 180 days time series with seasonality, trends & spikes
                base_demand = 20.0 + (loc_idx * 5.0) + (item_idx * 2.0)

                for day_idx in range(180):
                    c_date = start_history_date + timedelta(days=day_idx)
                    day_of_week = c_date.weekday()

                    # Weekly seasonality (higher demand on Monday/Tuesday)
                    season_factor = 1.25 if day_of_week in (0, 1) else 0.95

                    # Demand spike scenario in last 14 days for loc 0, item 0
                    if loc_idx == 0 and item_idx == 0 and day_idx >= 165:
                        spike_factor = 2.4
                    else:
                        spike_factor = 1.0

                    noise = random.uniform(0.85, 1.15)
                    cons_qty = max(
                        1.0,
                        round(base_demand * season_factor * spike_factor * noise, 1),
                    )

                    cr = ConsumptionRecord(
                        location_id=loc.id,
                        item_id=item.id,
                        date=c_date,
                        quantity=cons_qty,
                        source="AUTOMATED_TELEMETRY",
                    )
                    db.add(cr)
                    n_consumption_records += 1

                    # Add stock issue transaction every 5 days for 25x15 pairs = 375 * 36 = 13,500 transactions
                    if day_idx % 5 == 0:
                        tx_issue = InventoryTransaction(
                            location_id=loc.id,
                            item_id=item.id,
                            transaction_type=TransactionType.ISSUE.value,
                            quantity=cons_qty,
                            reference_id=f"ISSUE_{c_date}",
                            notes="Regular daily issue",
                            performed_by_id=users[1].id,
                        )
                        db.add(tx_issue)
                        n_transactions += 1

        counts["consumption_records"] = n_consumption_records
        counts["inventory_transactions"] = n_transactions

        # 6. Routes & Route Segments (100+ Segments)
        route_names = [
            "Jammu–Udhampur NH-44 Axis",
            "Udhampur–Banihal–Srinagar NH-44",
            "Rajouri–Poonch Forward Axis",
            "Akhnoor–Nowshera Feeder",
            "Srinagar–Baramulla–Uri NH-1",
            "Srinagar–Gulmarg Spur",
            "Anantnag–Pahalgam Axis",
            "Qazigund–Sonamarg High Road",
            "Kupwara–Tangdhar Feeder",
            "Bandipora–Ganderbal Valley Link",
        ]

        n_segments = 0
        for r_idx, r_name in enumerate(route_names):
            r = Route(
                id=uuid.uuid4(),
                name=r_name,
                status=(RouteStatus.ACTIVE.value if r_idx != 2 else RouteStatus.RESTRICTED.value),
                base_risk_score=round(0.15 + (r_idx * 0.03), 2),
            )
            db.add(r)

            for seg_i in range(1, 11):
                from_loc = loc_objects[(seg_i - 1) % len(loc_objects)]
                to_loc = loc_objects[seg_i % len(loc_objects)]
                seg = RouteSegment(
                    id=uuid.uuid4(),
                    route_id=r.id,
                    from_location_id=from_loc.id,
                    to_location_id=to_loc.id,
                    segment_order=seg_i,
                    distance_km=round(random.uniform(15.0, 65.0), 1),
                    travel_time_hours=round(random.uniform(0.8, 3.2), 1),
                    terrain_risk=round(random.uniform(0.1, 0.45), 2),
                    road_risk=round(random.uniform(0.05, 0.35), 2),
                )

                db.add(seg)
                n_segments += 1

        counts["routes"] = len(route_names)
        counts["route_segments"] = n_segments

        # 7. Weather Records (180 Days)
        n_weather = 0
        for loc in loc_objects[:10]:
            for d_offset in range(0, 180, 2):
                w_time = datetime.now(UTC) - timedelta(days=d_offset)
                # Elevation lapse from a Jammu autumn baseline, plus seasonal swing.
                seasonal = -12.0 * (d_offset / 180.0)
                temp = round(26.0 - (loc.elevation_m / 180.0) + seasonal + random.uniform(-4.0, 4.0), 1)
                sev = (
                    WeatherSeverity.SEVERE.value
                    if temp < -15.0
                    else (
                        WeatherSeverity.MODERATE.value if temp < -5.0 else WeatherSeverity.LOW.value
                    )
                )
                wr = WeatherRecord(
                    location_id=loc.id,
                    timestamp=w_time,
                    temperature_c=temp,
                    precipitation_mm=round(random.uniform(0.0, 45.0), 1),
                    wind_speed_kmh=round(random.uniform(10.0, 75.0), 1),
                    severity=sev,
                )
                db.add(wr)
                n_weather += 1

        counts["weather_records"] = n_weather

        # 8. Synthetic Shipments (1000+)
        n_shipments = 0
        for s_idx in range(1, 1001):
            src_loc = loc_objects[s_idx % len(loc_objects)]
            dst_loc = loc_objects[(s_idx + 3) % len(loc_objects)]
            veh = veh_objects[s_idx % len(veh_objects)]

            shp = Shipment(
                id=uuid.uuid4(),
                source_location_id=src_loc.id,
                destination_location_id=dst_loc.id,
                vehicle_id=veh.id,
                status=(
                    ShipmentStatus.PLANNED.value
                    if s_idx % 3 == 0
                    else (
                        ShipmentStatus.IN_TRANSIT.value
                        if s_idx % 2 == 0
                        else ShipmentStatus.DELIVERED.value
                    )
                ),
                priority=(
                    ShipmentPriority.URGENT.value
                    if s_idx % 5 == 0
                    else ShipmentPriority.ROUTINE.value
                ),
                planned_departure=datetime.now(UTC) - timedelta(hours=s_idx * 2),
                planned_arrival=datetime.now(UTC) + timedelta(hours=24 + s_idx),
            )
            db.add(shp)

            si = ShipmentItem(
                shipment_id=shp.id,
                item_id=item_objects[s_idx % len(item_objects)].id,
                quantity=round(random.uniform(100.0, 1500.0), 1),
            )
            db.add(si)
            n_shipments += 1

        counts["shipments"] = n_shipments

        # 9. Initial Alerts
        alerts = [
            Alert(
                severity=AlertSeverity.CRITICAL.value,
                alert_type="STOCKOUT_WARNING",
                title="Critical Stockout Warning: Diesel Fuel at Uri Forward Post",
                message="Demand surge detected. Projected stockout in 2.4 days.",
                entity_type="LOCATION",
                entity_id=loc_objects[0].id,
                status=AlertStatus.NEW.value,
            ),
            Alert(
                severity=AlertSeverity.HIGH.value,
                alert_type="SAFETY_STOCK_BREACH",
                title="Safety Stock Breach: Medical Kits at Poonch Forward Post",
                message="Current inventory 200.0 units is below safety stock threshold of 500.0 units.",
                entity_type="LOCATION",
                entity_id=loc_objects[1].id,
                status=AlertStatus.NEW.value,
            ),
        ]
        db.add_all(alerts)
        await db.flush()
        counts["alerts"] = len(alerts)

        await db.commit()
        return counts
