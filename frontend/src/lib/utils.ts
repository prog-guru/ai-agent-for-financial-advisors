// lib/utils.ts
export function cx(...c: (string | false | null | undefined)[]) {
    return c.filter(Boolean).join(" ");
  }
  
  export function timeRange(startISO: string, endISO: string) {
    const s = new Date(startISO);
    const e = new Date(endISO);
    const t = (d: Date) => d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    return `${t(s)} – ${t(e)}`;
  }
  
  import type { Person } from "@/lib/api";
  type Meeting = { id: string; title: string; start: string; end: string; attendees: Person[] };
  
  export function groupByDay(list: Meeting[]) {
    const label = (d: Date) => d.toLocaleDateString([], { day: "numeric", weekday: "long" }); // "8 Thursday"
    return list.reduce<Record<string, Meeting[]>>((acc, m) => {
      const k = label(new Date(m.start));
      (acc[k] ||= []).push(m);
      return acc;
    }, {});
  }
  