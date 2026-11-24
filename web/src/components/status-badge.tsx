import { Badge } from "@/components/ui/badge";
import { STATUS_LABELS } from "@/lib/format";
import type { VehicleStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const STYLES: Record<VehicleStatus, string> = {
  active: "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200",
  in_maintenance: "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200",
  inactive: "bg-muted text-muted-foreground",
};

export function StatusBadge({ status }: { status: VehicleStatus }) {
  return (
    <Badge variant="secondary" className={cn("font-medium", STYLES[status])}>
      {STATUS_LABELS[status]}
    </Badge>
  );
}
