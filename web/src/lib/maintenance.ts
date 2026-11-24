import { formatDate, formatKm } from "@/lib/format";
import type { UpcomingMaintenance } from "@/lib/types";

/** Why an item is listed: the trigger that comes first, in plain words. */
export function maintenanceReason(item: UpcomingMaintenance): string {
  if (item.reason === "km" && item.km_remaining !== null) {
    return item.km_remaining < 0
      ? `${formatKm(-item.km_remaining)} past the service interval`
      : `Due in ${formatKm(item.km_remaining)}`;
  }
  const days = item.days_until_due;
  const when = item.next_due_date ? ` (${formatDate(item.next_due_date)})` : "";
  if (days < 0) return `${-days} days past due${when}`;
  if (days === 0) return `Due today${when}`;
  return `Due in ${days} days${when}`;
}
