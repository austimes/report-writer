import { query, mutation } from "../_generated/server";
import { v } from "convex/values";

const LOCK_EXPIRY_MS = 7200000;

type Lock = {
  _id: any;
  _creationTime: number;
  projectId: any;
  resourceType: "section" | "block" | "thread";
  resourceId: string;
  userId: any;
  lockedAt: number;
};

function isLockExpired(lock: Lock): boolean {
  return lock.lockedAt + LOCK_EXPIRY_MS < Date.now();
}

export const acquireLock = mutation({
  args: {
    projectId: v.id("projects"),
    resourceType: v.union(
      v.literal("section"),
      v.literal("block"),
      v.literal("thread")
    ),
    resourceId: v.string(),
  },
  handler: async (ctx, { projectId, resourceType, resourceId }) => {
    const userId = await ctx.auth.getUserIdentity();
    if (!userId) {
      throw new Error("Not authenticated");
    }

    const user = await ctx.db
      .query("users")
      .withIndex("by_email", (q) => q.eq("email", userId.email!))
      .unique();

    if (!user) {
      throw new Error("User not found");
    }

    const existingLock = await ctx.db
      .query("locks")
      .withIndex("by_resource", (q) =>
        q.eq("resourceType", resourceType).eq("resourceId", resourceId)
      )
      .unique();

    if (existingLock) {
      if (!isLockExpired(existingLock)) {
        if (existingLock.userId !== user._id) {
          const lockOwner = await ctx.db.get(existingLock.userId);
          throw new Error(
            `Resource is locked by ${lockOwner?.name || "another user"}`
          );
        }
        await ctx.db.patch(existingLock._id, {
          lockedAt: Date.now(),
        });
        return await ctx.db.get(existingLock._id);
      } else {
        await ctx.db.delete(existingLock._id);
      }
    }

    const lockId = await ctx.db.insert("locks", {
      projectId,
      resourceType,
      resourceId,
      userId: user._id,
      lockedAt: Date.now(),
    });

    return await ctx.db.get(lockId);
  },
});

export const releaseLock = mutation({
  args: { lockId: v.id("locks") },
  handler: async (ctx, { lockId }) => {
    await ctx.db.delete(lockId);
  },
});

export const refreshLock = mutation({
  args: { lockId: v.id("locks") },
  handler: async (ctx, { lockId }) => {
    await ctx.db.patch(lockId, {
      lockedAt: Date.now(),
    });
    return await ctx.db.get(lockId);
  },
});

export const getLocksForProject = query({
  args: { projectId: v.id("projects") },
  handler: async (ctx, { projectId }) => {
    const locks = await ctx.db
      .query("locks")
      .withIndex("by_project", (q) => q.eq("projectId", projectId))
      .collect();

    return locks.filter((lock) => !isLockExpired(lock));
  },
});

export const getLockForResource = query({
  args: {
    resourceType: v.union(
      v.literal("section"),
      v.literal("block"),
      v.literal("thread")
    ),
    resourceId: v.string(),
  },
  handler: async (ctx, { resourceType, resourceId }) => {
    const lock = await ctx.db
      .query("locks")
      .withIndex("by_resource", (q) =>
        q.eq("resourceType", resourceType).eq("resourceId", resourceId)
      )
      .unique();

    if (!lock || isLockExpired(lock)) {
      return null;
    }

    return lock;
  },
});
