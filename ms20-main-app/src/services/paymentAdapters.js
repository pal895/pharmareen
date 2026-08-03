export class PaymentAdapter {
  constructor(name) {
    this.name = name;
  }

  request() {
    throw new Error(`${this.name} payment adapter has no request implementation`);
  }
}

export class CashPaymentAdapter extends PaymentAdapter {
  constructor() {
    super("cash");
  }

  request({ transactionId }) {
    return {
      providerReference: `cash-${transactionId}`,
      status: "confirmed",
      reason: "cash_recorded"
    };
  }
}

export class ManualPaymentAdapter extends PaymentAdapter {
  constructor() {
    super("manual");
  }

  request({ transactionId, paymentMethod }) {
    return {
      providerReference: `manual-${paymentMethod}-${transactionId}`,
      status: "confirmed",
      reason: "owner_recorded"
    };
  }
}

export class DeferredPaymentAdapter extends PaymentAdapter {
  constructor() {
    super("deferred");
  }

  request({ transactionId }) {
    return {
      providerReference: `deferred-${transactionId}`,
      status: "pending",
      reason: "supplier_settlement_due"
    };
  }
}

export class SimulatorPaymentAdapter extends PaymentAdapter {
  constructor({ scenario = "success" } = {}) {
    super("simulator");
    this.scenario = scenario;
  }

  setScenario(scenario) {
    this.scenario = scenario;
  }

  request({ transactionId }) {
    const outcomes = {
      success: ["confirmed", "simulated_success"],
      timeout: ["pending", "simulated_timeout"],
      cancellation: ["cancelled", "simulated_cancellation"],
      wrong_pin: ["failed", "simulated_wrong_pin"],
      insufficient_balance: ["failed", "simulated_insufficient_balance"],
      delayed_confirmation: ["pending", "simulated_delayed_confirmation"],
      duplicate_callback: ["pending", "simulated_duplicate_callback"],
      failed_payment: ["failed", "simulated_failed_payment"],
      refund: ["refunded", "simulated_refund"],
      reversal: ["reversed", "simulated_reversal"]
    };
    const [status, reason] = outcomes[this.scenario] || outcomes.failed_payment;
    return {
      providerReference: `sim-${this.scenario}-${transactionId}`,
      status,
      reason
    };
  }
}
