// Shapes of the fleet-manager API responses used by the dashboard (see the API's /docs).

export type Role = "admin" | "viewer";

export type CurrentUser = {
  id: number;
  email: string;
  role: Role;
};

export type VehicleStatus = "active" | "in_maintenance" | "inactive";
export type VehicleType = "car" | "van" | "truck" | "motorcycle";
export type MaintenanceType =
  | "oil_change"
  | "tires"
  | "brakes"
  | "inspection"
  | "repair"
  | "other";

export const VEHICLE_STATUSES: readonly VehicleStatus[] = ["active", "in_maintenance", "inactive"];
export const VEHICLE_TYPES: readonly VehicleType[] = ["car", "van", "truck", "motorcycle"];

export type Page<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

export type DriverSummary = {
  id: number;
  full_name: string;
  license_number: string;
  license_expiry: string;
};

export type Driver = DriverSummary & {
  phone: string;
  is_active: boolean;
  created_at: string;
};

export type Vehicle = {
  id: number;
  plate: string;
  brand: string;
  model: string;
  year: number;
  vehicle_type: VehicleType;
  status: VehicleStatus;
  odometer_km: number;
  assigned_driver: DriverSummary | null;
  created_at: string;
  updated_at: string;
};

export type MaintenanceRecord = {
  id: number;
  vehicle_id: number;
  maintenance_type: MaintenanceType;
  performed_at: string;
  odometer_km: number;
  cost: string;
  notes: string | null;
  next_due_km: number | null;
  next_due_date: string | null;
};

export type VehicleDetail = Vehicle & {
  recent_maintenance: MaintenanceRecord[];
};

export type Summary = {
  as_of: string;
  vehicles: { total: number; by_status: Record<VehicleStatus, number> };
  drivers: { active: number; licenses_expiring_soon: number; licenses_expired: number };
  maintenance: { overdue: number; vehicles_with_overdue: number };
};

export type UpcomingMaintenance = {
  vehicle_id: number;
  plate: string;
  brand: string;
  model: string;
  vehicle_status: VehicleStatus;
  maintenance_type: MaintenanceType;
  last_performed_at: string;
  odometer_km: number;
  next_due_date: string | null;
  next_due_km: number | null;
  km_remaining: number | null;
  days_until_due: number;
  reason: "date" | "km";
  state: "overdue" | "upcoming";
  km_estimate_used: boolean;
};

export type UpcomingMaintenanceResponse = {
  as_of: string;
  days: number;
  items: UpcomingMaintenance[];
};

export type MonthlyCost = {
  month: string;
  maintenance: string;
  fuel: string;
  total: string;
};

export type MonthlyCostsResponse = {
  months: MonthlyCost[];
  totals: { maintenance: string; fuel: string; total: string };
};
