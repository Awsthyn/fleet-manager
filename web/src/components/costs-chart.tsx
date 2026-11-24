"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatMoney, formatMonth } from "@/lib/format";
import type { MonthlyCost } from "@/lib/types";

const compact = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });

/** Monthly maintenance vs fuel costs, side by side. */
export function CostsChart({ months }: { months: MonthlyCost[] }) {
  const data = months.map((m) => ({
    month: formatMonth(m.month),
    maintenance: Number(m.maintenance),
    fuel: Number(m.fuel),
  }));

  return (
    <div className="h-72 w-full" role="img" aria-label="Monthly maintenance and fuel costs">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--border)" />
          <XAxis dataKey="month" tickLine={false} axisLine={false} fontSize={12} />
          <YAxis
            tickLine={false}
            axisLine={false}
            fontSize={12}
            width={48}
            tickFormatter={(value: number) => compact.format(value)}
          />
          <Tooltip
            cursor={{ fill: "var(--muted)" }}
            formatter={(value) => formatMoney(Number(value))}
            contentStyle={{
              background: "var(--popover)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius)",
              color: "var(--popover-foreground)",
              fontSize: 12,
            }}
          />
          <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
          <Bar dataKey="maintenance" name="Maintenance" fill="var(--chart-1)" radius={[4, 4, 0, 0]} />
          <Bar dataKey="fuel" name="Fuel" fill="var(--chart-2)" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
