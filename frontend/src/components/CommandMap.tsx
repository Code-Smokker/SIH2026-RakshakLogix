import React, { useEffect, useMemo, useState } from 'react';
import {
  CircleMarker,
  MapContainer,
  Polyline,
  Popup,
  TileLayer,
  useMap,
} from 'react-leaflet';
import type { LatLngBoundsExpression, LatLngExpression } from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { ApiError } from '../api/client';
import { authApi } from '../api/authApi';
import {
  dashboardApi,
  LocationMapPin,
  RouteMapLine,
} from '../api/dashboardApi';

type MapFocus = 'network' | 'locations' | 'routes';
type LayerMode = 'all' | 'critical' | 'routes' | 'locations';

const BRIEFING_PINS: LocationMapPin[] = [
  { id: 'srinagar', name: 'Srinagar Divisional Logistics Hub', type: 'HUB', latitude: 34.0837, longitude: 74.7973, status: 'ACTIVE', risk_severity: 'LOW', stockout_risk_items_count: 0 },
  { id: 'udhampur', name: 'Udhampur Northern Command Depot', type: 'DEPOT', latitude: 32.915, longitude: 75.1419, status: 'ACTIVE', risk_severity: 'LOW', stockout_risk_items_count: 0 },
  { id: 'jammu', name: 'Jammu Satwari Supply Depot', type: 'DEPOT', latitude: 32.7266, longitude: 74.857, status: 'ACTIVE', risk_severity: 'LOW', stockout_risk_items_count: 0 },
  { id: 'uri', name: 'Uri Forward Post', type: 'FORWARD_POST', latitude: 34.087, longitude: 74.05, status: 'ACTIVE', risk_severity: 'CRITICAL', stockout_risk_items_count: 3 },
  { id: 'poonch', name: 'Poonch Forward Post', type: 'FORWARD_POST', latitude: 33.767, longitude: 74.0925, status: 'ACTIVE', risk_severity: 'HIGH', stockout_risk_items_count: 2 },
  { id: 'rajouri', name: 'Rajouri Brigade Hub', type: 'HUB', latitude: 33.3766, longitude: 74.309, status: 'ACTIVE', risk_severity: 'HIGH', stockout_risk_items_count: 1 },
  { id: 'baramulla', name: 'Baramulla Forward Hub', type: 'HUB', latitude: 34.198, longitude: 74.3436, status: 'ACTIVE', risk_severity: 'LOW', stockout_risk_items_count: 0 },
  { id: 'pahalgam', name: 'Pahalgam High Post', type: 'FORWARD_POST', latitude: 34.0161, longitude: 75.315, status: 'ACTIVE', risk_severity: 'HIGH', stockout_risk_items_count: 1 },
];

const TILES = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const ATTRIBUTION = '&copy; OpenStreetMap contributors';

function riskColor(severity: string): string {
  if (severity === 'CRITICAL') return '#9f2d2d';
  if (severity === 'HIGH') return '#8a6a2f';
  return '#3f5135';
}

function routeColor(route: RouteMapLine): string {
  if (route.status === 'BLOCKED' || route.risk_score >= 0.45) return '#9f2d2d';
  if (route.status === 'RESTRICTED' || route.risk_score >= 0.3) return '#8a6a2f';
  return '#3f5135';
}

function FitNetwork({ positions }: { positions: LatLngExpression[] }) {
  const map = useMap();
  useEffect(() => {
    if (positions.length === 0) return;
    const bounds: LatLngBoundsExpression = positions.map((position) => {
      const [latitude, longitude] = position as [number, number];
      return [latitude, longitude] as [number, number];
    });
    map.fitBounds(bounds, { padding: [28, 28], maxZoom: 9 });
    const timer = window.setTimeout(() => map.invalidateSize(), 80);
    return () => window.clearTimeout(timer);
  }, [map, positions]);

  useEffect(() => {
    const parent = map.getContainer().parentElement;
    if (!parent) return;
    const observer = new ResizeObserver(() => map.invalidateSize());
    observer.observe(parent);
    return () => observer.disconnect();
  }, [map]);

  return null;
}

async function loadLiveMap() {
  try {
    return await dashboardApi.getMap();
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      await authApi.login({
        email: 'planner@rakshaklogix.dev',
        password: 'Planner@123456',
      });
      return dashboardApi.getMap();
    }
    throw error;
  }
}

export const CommandMap: React.FC<{ focus?: MapFocus }> = ({ focus = 'network' }) => {
  const [pins, setPins] = useState<LocationMapPin[]>(BRIEFING_PINS);
  const [routes, setRoutes] = useState<RouteMapLine[]>([]);
  const [source, setSource] = useState<'live' | 'briefing'>('briefing');
  const [mode, setMode] = useState<LayerMode>(focus === 'routes' ? 'routes' : 'all');

  useEffect(() => {
    let stopped = false;
    let timer = 0;

    const pull = async () => {
      try {
        const data = await loadLiveMap();
        if (stopped) return;
        if (data.locations.length > 0) {
          setPins(data.locations);
          setRoutes(data.routes);
          setSource('live');
          return;
        }
      } catch {
        if (!stopped) setSource('briefing');
      }
      if (!stopped) timer = window.setTimeout(pull, 8000);
    };

    pull();
    return () => {
      stopped = true;
      window.clearTimeout(timer);
    };
  }, []);

  useEffect(() => {
    const onFilter = (event: Event) => {
      const detail = (event as CustomEvent<LayerMode>).detail;
      if (detail === 'all' || detail === 'critical' || detail === 'routes' || detail === 'locations') {
        setMode(detail);
      }
    };
    window.addEventListener('rl-map-filter', onFilter);
    return () => window.removeEventListener('rl-map-filter', onFilter);
  }, []);

  const byId = useMemo(() => {
    const index = new Map<string, LocationMapPin>();
    pins.forEach((pin) => index.set(String(pin.id), pin));
    return index;
  }, [pins]);

  const visiblePins = pins.filter((pin) => {
    if (mode === 'routes') return false;
    if (mode === 'critical') return pin.risk_severity === 'CRITICAL' || pin.risk_severity === 'HIGH';
    return true;
  });

  const lines = useMemo(() => {
    if (mode === 'locations') return [];
    return routes
      .map((route) => {
        const positions = route.segments.flatMap((segment) => {
          const from = byId.get(segment.from_location_id);
          const to = byId.get(segment.to_location_id);
          if (!from || !to) return [];
          return [[
            [from.latitude, from.longitude] as LatLngExpression,
            [to.latitude, to.longitude] as LatLngExpression,
          ]];
        });
        return { route, positions };
      })
      .filter((line) => line.positions.length > 0);
  }, [routes, byId, mode]);

  const fitPositions: LatLngExpression[] = (visiblePins.length ? visiblePins : pins).map(
    (pin) => [pin.latitude, pin.longitude],
  );

  return (
    <div className="rl-command-map">
      <MapContainer
        center={[33.6, 74.8]}
        zoom={8}
        scrollWheelZoom
        style={{ height: '100%', width: '100%' }}
      >
        <TileLayer attribution={ATTRIBUTION} url={TILES} />
        <FitNetwork positions={fitPositions} />
        {lines.map(({ route, positions }) =>
          positions.map((pair, index) => (
            <Polyline
              key={`${route.id}-${index}`}
              positions={pair}
              pathOptions={{ color: routeColor(route), weight: 3, opacity: 0.85 }}
            >
              <Popup>
                <strong>{route.name}</strong>
                <br />
                {route.status} · risk {route.risk_score.toFixed(2)}
              </Popup>
            </Polyline>
          )),
        )}
        {visiblePins.map((pin) => (
          <CircleMarker
            key={pin.id}
            center={[pin.latitude, pin.longitude]}
            radius={pin.risk_severity === 'CRITICAL' ? 9 : 7}
            pathOptions={{
              color: '#f7f4ea',
              weight: 2,
              fillColor: riskColor(pin.risk_severity),
              fillOpacity: 0.95,
            }}
          >
            <Popup>
              <strong>{pin.name}</strong>
              <br />
              {pin.type} · {pin.status}
              <br />
              Risk {pin.risk_severity}
              {pin.stockout_risk_items_count > 0
                ? ` · ${pin.stockout_risk_items_count} items at safety stock`
                : ''}
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>
      <div className="rl-map-legend">
        <span>{source === 'live' ? 'Live network' : 'Briefing sample'}</span>
        <span><i style={{ background: '#3f5135' }} /> Nominal</span>
        <span><i style={{ background: '#8a6a2f' }} /> High</span>
        <span><i style={{ background: '#9f2d2d' }} /> Critical</span>
        <button type="button" onClick={() => setMode('all')}>All</button>
        <button type="button" onClick={() => setMode('critical')}>Risk</button>
        <button type="button" onClick={() => setMode('routes')}>Routes</button>
        <button type="button" onClick={() => setMode('locations')}>Posts</button>
      </div>
    </div>
  );
};
