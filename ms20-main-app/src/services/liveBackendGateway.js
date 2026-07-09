import { LiveBackendRoutes } from "../contracts/integrationContracts.js";

const DEFAULT_LOCAL_BACKEND = "http://127.0.0.1:5000";

function trimSlash(value) {
  return String(value || "").replace(/\/+$/, "");
}

function inferBackendBaseUrl() {
  if (typeof window === "undefined") return DEFAULT_LOCAL_BACKEND;
  const configured = window.__MS20_BACKEND_BASE_URL__;
  if (configured) return trimSlash(configured);

  const { protocol, hostname, port, origin } = window.location;
  if (port === "5000" || port === "") return origin;
  if (hostname === "127.0.0.1" || hostname === "localhost") {
    return `${protocol}//${hostname}:5000`;
  }
  return origin;
}

function summarizeReadiness(payload) {
  if (!payload || typeof payload !== "object") {
    return { status: "unknown", sheets: false, baileys: false, offline: false };
  }
  return {
    status: payload.status || "unknown",
    sheets: Boolean(payload.google_sheets_connected || payload.pharmacy_registry_connected),
    baileys: Boolean(payload.baileys_confirmed || payload.baileys_route_exists),
    offline: Boolean(payload.offline_app_loads),
    blocked: Array.isArray(payload.blocked) ? payload.blocked : []
  };
}

export class LiveBackendGateway {
  constructor({ baseUrl } = {}) {
    this.baseUrl = trimSlash(baseUrl || inferBackendBaseUrl());
    this.lastSnapshot = null;
  }

  urlFor(path) {
    if (/^https?:\/\//i.test(path)) return path;
    return `${this.baseUrl}${path.startsWith("/") ? path : `/${path}`}`;
  }

  endpointLinks() {
    return Object.fromEntries(
      Object.entries(LiveBackendRoutes).map(([name, path]) => [name, this.urlFor(path)])
    );
  }

  async statusSnapshot() {
    const [health, version, readiness, offlineApp] = await Promise.all([
      this.requestJson(LiveBackendRoutes.health),
      this.requestJson(LiveBackendRoutes.debugVersion),
      this.requestJson(LiveBackendRoutes.readiness),
      this.requestText(LiveBackendRoutes.offlineApp)
    ]);

    const readinessSummary = summarizeReadiness(readiness.data);
    const snapshot = {
      checkedAt: new Date().toISOString(),
      baseUrl: this.baseUrl,
      health,
      version,
      readiness,
      readinessSummary,
      offlineApp: {
        ...offlineApp,
        route: LiveBackendRoutes.offlineApp,
        url: this.urlFor(LiveBackendRoutes.offlineApp)
      },
      routes: this.endpointLinks(),
      writeMode: "safe_queue_only",
      tokenImpact: "zero_openai_api_tokens"
    };
    this.lastSnapshot = snapshot;
    return snapshot;
  }

  async requestJson(path, options = {}) {
    const response = await this.request(path, {
      ...options,
      headers: { Accept: "application/json", ...(options.headers || {}) }
    });
    if (!response.ok) return response;
    try {
      return { ...response, data: JSON.parse(response.body || "{}") };
    } catch (error) {
      return { ...response, ok: false, error: `Invalid JSON: ${error.message}` };
    }
  }

  async requestText(path, options = {}) {
    return this.request(path, {
      ...options,
      headers: { Accept: "text/html,text/plain,*/*", ...(options.headers || {}) }
    });
  }

  async request(path, { method = "GET", body, headers = {}, timeoutMs = 2200 } = {}) {
    if (typeof fetch !== "function") {
      return { ok: false, status: 0, route: path, url: this.urlFor(path), error: "fetch unavailable" };
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(this.urlFor(path), {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal
      });
      const text = await response.text();
      return {
        ok: response.ok,
        status: response.status,
        route: path,
        url: this.urlFor(path),
        body: text
      };
    } catch (error) {
      return {
        ok: false,
        status: 0,
        route: path,
        url: this.urlFor(path),
        error: error.name === "AbortError" ? "timeout" : error.message
      };
    } finally {
      clearTimeout(timer);
    }
  }

  prepareAction(card, liveStatus = this.lastSnapshot) {
    const type = card?.type || "UnknownCard";
    const targets = {
      SaleCard: "saleEngineAdapter",
      RestockCard: "stockEngineAdapter",
      StockCorrectionCard: "stockEngineAdapter",
      ReportCard: "reportEngineAdapter",
      InvoiceCard: "invoiceEngineAdapter",
      OnboardingCard: "onboardingEngineAdapter",
      SyncReviewCard: "syncEngineAdapter"
    };
    const target = targets[type] || "commandParserAdapter";
    const backendReady = Boolean(liveStatus?.health?.ok);
    const route = type === "ReportCard" ? LiveBackendRoutes.dailyReport : LiveBackendRoutes.baileysWebhook;

    return {
      target,
      route,
      url: this.urlFor(route),
      backendReady,
      writeMode: "safe_queue_only",
      aiUsed: false,
      summary: backendReady
        ? "Live backend detected. Confirm queues this action until safe sync is enabled."
        : "Backend not detected. Confirm stores this safely in the offline queue."
    };
  }
}
