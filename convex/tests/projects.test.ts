import { describe, it, expect, beforeEach } from "vitest";
import { convexTest } from "convex-test";
import schema from "../schema";
import { Id } from "convex/values";
import * as projectsModule from "../tables/projects";

describe("Projects table", () => {
  let t: ReturnType<typeof convexTest>;
  let userId: Id<"users">;

  beforeEach(async () => {
    t = convexTest(schema, {});

    userId = await t.run(async (ctx) => {
      return await ctx.db.insert("users", {
        email: "test@example.com",
        name: "Test User",
        createdAt: Date.now(),
      });
    });
  });

  it("creates a project for an existing user", async () => {
    const projectId = await t.mutation(projectsModule.create, {
      ownerId: userId,
      name: "My Project",
      description: "Test project",
    });

    const project = await t.run(async (ctx) => ctx.db.get(projectId));

    expect(project).toBeTruthy();
    expect(project?.ownerId).toEqual(userId);
    expect(project?.name).toBe("My Project");
    expect(project?.description).toBe("Test project");
    expect(project?.archived).toBe(false);
    expect(typeof project?.createdAt).toBe("number");
  });

  it("fails to create project when owner does not exist", async () => {
    const fakeUserId = await t.run(async (ctx) => {
      const id = await ctx.db.insert("users", {
        email: "temp@example.com",
        name: "Temp",
        createdAt: Date.now(),
      });
      await ctx.db.delete(id);
      return id;
    });

    await expect(
      t.mutation(projectsModule.create, {
        ownerId: fakeUserId,
        name: "Should fail",
        description: "Should fail",
      })
    ).rejects.toThrow(/User .* not found/);
  });

  it("lists projects for a user", async () => {
    const [project1, project2] = await t.run(async (ctx) => {
      const id1 = await ctx.db.insert("projects", {
        ownerId: userId,
        name: "P1",
        description: "First",
        createdAt: Date.now(),
        archived: false,
      });
      const id2 = await ctx.db.insert("projects", {
        ownerId: userId,
        name: "P2",
        description: "Second",
        createdAt: Date.now(),
        archived: false,
      });
      return [id1, id2];
    });

    const projects = await t.query(projectsModule.listByUser, { userId });

    const ids = projects.map((p) => p._id);
    expect(ids).toContain(project1);
    expect(ids).toContain(project2);
  });

  it("updates project name and description", async () => {
    const projectId = await t.mutation(projectsModule.create, {
      ownerId: userId,
      name: "Old Name",
      description: "Old desc",
    });

    await t.mutation(projectsModule.update, {
      id: projectId,
      name: "New Name",
      description: "New desc",
    });

    const project = await t.run(async (ctx) => ctx.db.get(projectId));
    expect(project?.name).toBe("New Name");
    expect(project?.description).toBe("New desc");
  });

  it("archives a project", async () => {
    const projectId = await t.mutation(projectsModule.create, {
      ownerId: userId,
      name: "To archive",
      description: "Test",
    });

    await t.mutation(projectsModule.archive, { id: projectId });

    const project = await t.run(async (ctx) => ctx.db.get(projectId));
    expect(project?.archived).toBe(true);
  });
});
