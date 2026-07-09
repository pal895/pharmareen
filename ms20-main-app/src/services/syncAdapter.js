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

  async syncPending() {
    const pending = this.queue.list().filter((item) => item.status === "pending");
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
