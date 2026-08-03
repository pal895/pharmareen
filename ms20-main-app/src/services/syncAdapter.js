export class SyncAdapter {
  constructor({ queue, cloudGateway }) {
    this.queue = queue;
    this.cloudGateway = cloudGateway;
    this.lastSync = null;
    this.lastConflict = null;
  }

  queueAction(action) {
    return this.queue.add(action);
  }

  async syncPending({ excludeTypes = [] } = {}) {
    const excluded = new Set(excludeTypes);
    const pending = this.queue.list().filter((item) => item.status === "pending" && !excluded.has(item.type));
    const synced = [];
    for (const action of pending) {
      await this.cloudGateway.saveAction(action);
      this.queue.update(action.id, {
        status: "synced",
        syncedAt: new Date().toISOString()
      });
      synced.push(action.id);
    }
    this.lastSync = new Date().toISOString();
    return {
      synced,
      pending: this.queue.pendingCount(),
      lastSync: this.lastSync,
      conflicts: this.lastConflict ? [this.lastConflict] : []
    };
  }

  async syncOne(actionId) {
    const action = this.queue.list().find((item) => item.id === actionId && item.status === "pending");
    if (!action) return { synced: false, actionId, message: "This item is not waiting." };
    try {
      const result = await this.cloudGateway.saveAction(action);
      const syncedAt = new Date().toISOString();
      this.queue.update(action.id, { status: "synced", syncedAt, syncMessage: result.message || "Saved." });
      this.lastSync = syncedAt;
      this.lastConflict = null;
      return { synced: true, actionId, lastSync: syncedAt, result };
    } catch (error) {
      const message = error?.message || "The item was not sent. It is still waiting safely.";
      this.queue.update(action.id, { status: "pending", lastSyncError: message });
      this.createConflictReview(action, message);
      return { synced: false, actionId, message };
    }
  }

  createConflictReview(action, reason) {
    this.lastConflict = {
      id: `conflict-${Date.now()}`,
      actionId: action.id,
      reason,
      status: "needs_review"
    };
    return this.lastConflict;
  }

  status() {
    return {
      pending: this.queue.pendingCount(),
      lastSync: this.lastSync,
      conflict: this.lastConflict
    };
  }
}
