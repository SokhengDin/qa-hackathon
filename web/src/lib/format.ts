// Pin locale + timezone explicitly so server-rendered and client-rendered
// timestamps always match — using the host's default locale/timezone here
// causes hydration mismatches when server and client differ (see React
// hydration warnings on toLocaleString()/toLocaleTimeString()).

export function formatTime(date: Date): string {
  return date.toLocaleTimeString("en-US", { timeZone: "UTC" });
}

export function formatDateTime(date: Date): string {
  return date.toLocaleString("en-US", { timeZone: "UTC" });
}
