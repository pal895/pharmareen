import { LiveBackendRoutes, RouteSlots } from "../contracts/integrationContracts.js";

export function listRouteSlots(liveStatus = null) {
  const appRoutes = Object.entries(RouteSlots).map(([name, path]) => ({
    name,
    path,
    status: "frontend_reserved"
  }));

  const liveRoutes = Object.entries(LiveBackendRoutes).map(([name, path]) => ({
    name: `live_${name}`,
    path,
    url: liveStatus?.routes?.[name] || path,
    status: liveRouteStatus(name, liveStatus)
  }));

  return [...appRoutes, ...liveRoutes];
}

export function resolveOfflineSlot(liveStatus = null) {
  return {
    preferred: RouteSlots.appOffline,
    compatibility: RouteSlots.offline,
    liveCompatibility: LiveBackendRoutes.offlineApp,
    url: liveStatus?.offlineApp?.url || liveStatus?.routes?.offlineApp || LiveBackendRoutes.offlineApp,
    status: liveStatus?.offlineApp?.ok ? "connected" : "available_when_backend_runs",
    note: "Existing offline app is mounted through the live backend route without rebuilding it."
  };
}

function liveRouteStatus(name, liveStatus) {
  if (!liveStatus) return "not_checked";
  if (name === "health") return liveStatus.health?.ok ? "connected" : "not_reachable";
  if (name === "debugVersion") return liveStatus.version?.ok ? "connected" : "not_reachable";
  if (name === "readiness") return liveStatus.readiness?.ok ? "connected" : "not_reachable";
  if (name === "offlineApp") return liveStatus.offlineApp?.ok ? "connected" : "not_reachable";
  if (name === "baileysWebhook") return liveStatus.readinessSummary?.baileys ? "confirmed" : "route_reserved";
  if (name === "dailyReport") return liveStatus.health?.ok ? "route_reserved" : "not_checked";
  return "route_reserved";
}
