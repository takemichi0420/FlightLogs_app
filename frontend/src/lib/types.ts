export type AuthUser = {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
};

export type Paginated<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export type Aircraft = {
  id: number;
  registration_number: string;
  is_certified: boolean;
  remote_id: string;
  model: string;
  serial_number: string;
  name: string;
  initial_total_flight_seconds: number;
  current_total_flight_seconds: number;
};

export type Pilot = {
  id: number;
  name: string;
  license_number: string;
  organization: string;
  signature_image: string | null;
};

export type AnalysisJob = {
  id: string;
  flight_record_id: number;
  status: "queued" | "running" | "succeeded" | "failed";
  error_message: string;
};

export type MavlinkLogEntry = {
  id: number;
  size: number;
  time_utc: number;
  num_logs: number;
  last_log_num: number;
};

export type AltitudeProfilePoint = {
  time_s: number;
  altitude_m: number;
  relative_altitude_m: number;
  speed_mps: number | null;
  x_m: number;
  y_m: number;
  lat?: number;
  lng?: number;
};

export type WaypointPoint = {
  seq: number;
  command: number | null;
  frame: number | null;
  lat: number;
  lng: number;
  altitude_m: number;
  relative_altitude_m: number;
  x_m: number;
  y_m: number;
};

export type FlightAnalysis = {
  arm_at_utc: string | null;
  disarm_at_utc: string | null;
  max_altitude_m: number | null;
  max_speed_mps: number | null;
  max_distance_m: number | null;
  battery_start_voltage: number | null;
  battery_end_voltage: number | null;
  battery_min_voltage: number | null;
  gps_min_satellites: number | null;
  gps_max_hdop: number | null;
  warning_messages: string[];
  error_messages: string[];
  summary_json: {
    altitude_profile?: AltitudeProfilePoint[];
    altitude_profile_count?: number;
    waypoints?: WaypointPoint[];
    waypoint_count?: number;
    [key: string]: unknown;
  };
};

export type FlightModeSpan = {
  id: number;
  mode_name: string;
  start_at_utc: string | null;
  end_at_utc: string | null;
  duration_seconds: number | null;
};

export type GeneratedAsset = {
  id: number;
  asset_type: string;
  file: string;
  generated_at: string;
};

export type FlightRecord = {
  id: number;
  aircraft: number | null;
  pilot: number | null;
  status: "uploaded" | "analyzing" | "analysis_failed" | "draft" | "finalized";
  source_original_name: string;
  source_log_type: string;
  vehicle_type: string;
  flight_date: string | null;
  takeoff_at_utc: string | null;
  landing_at_utc: string | null;
  duration_seconds: number | null;
  takeoff_lat: number | null;
  takeoff_lng: number | null;
  takeoff_address: string;
  landing_lat: number | null;
  landing_lng: number | null;
  landing_address: string;
  purpose: string;
  special_flight_types: string;
  route_summary: string;
  official_weather: string;
  official_temperature_c: number | null;
  official_wind_speed_mps: number | null;
  reference_weather: string;
  reference_temperature_c: number | null;
  reference_wind_speed_mps: number | null;
  reference_station_name: string;
  reference_source: string;
  safety_notes: string;
  article_notes: string;
  pilot_signature: string;
  diagnostic_grade: string;
  review_required: boolean;
  finalized_at: string | null;
  analysis: FlightAnalysis | null;
  mode_spans: FlightModeSpan[];
  generated_assets: GeneratedAsset[];
  analysis_job: AnalysisJob | null;
};
