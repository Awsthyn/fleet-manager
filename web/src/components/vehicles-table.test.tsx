import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { NewVehicleButton, VehiclesTable } from "@/components/vehicles-table";
import type { Vehicle } from "@/lib/types";

const VEHICLES: Vehicle[] = [
  {
    id: 1,
    plate: "ZZ101AA",
    brand: "Toyota",
    model: "Hilux",
    year: 2022,
    vehicle_type: "truck",
    status: "active",
    odometer_km: 48200,
    assigned_driver: {
      id: 3,
      full_name: "Driver Example",
      license_number: "LIC-0001",
      license_expiry: "2027-04-30",
    },
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
  {
    id: 2,
    plate: "ZZ102BB",
    brand: "Renault",
    model: "Kangoo",
    year: 2020,
    vehicle_type: "van",
    status: "in_maintenance",
    odometer_km: 91000,
    assigned_driver: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

function renderVehiclesPage(canEdit: boolean) {
  return render(
    <>
      <NewVehicleButton canEdit={canEdit} />
      <VehiclesTable vehicles={VEHICLES} canEdit={canEdit} />
    </>,
  );
}

describe("vehicles list permissions", () => {
  it("shows no create or edit controls to a viewer", () => {
    // Guards the read-only role: rejects offering a viewer actions the API would refuse (403).
    renderVehiclesPage(false);

    expect(screen.getByText("ZZ101AA")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /new vehicle/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /edit/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("shows create and per-row edit controls to an admin", () => {
    // Guards the check from the other side: rejects hiding admin controls from everyone.
    renderVehiclesPage(true);

    expect(screen.getByRole("link", { name: /new vehicle/i })).toHaveAttribute(
      "href",
      "/vehicles/new",
    );
    expect(screen.getByRole("link", { name: "Edit ZZ101AA" })).toHaveAttribute(
      "href",
      "/vehicles/1/edit",
    );
    expect(screen.getAllByRole("link", { name: /^edit /i })).toHaveLength(VEHICLES.length);
  });
});
