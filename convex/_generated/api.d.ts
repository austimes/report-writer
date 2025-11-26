/* eslint-disable */
/**
 * Generated `api` utility.
 *
 * THIS CODE IS AUTOMATICALLY GENERATED.
 *
 * To regenerate, run `npx convex dev`.
 * @module
 */

import type * as debugAuth from "../debugAuth.js";
import type * as features_agent from "../features/agent.js";
import type * as features_locking from "../features/locking.js";
import type * as tables_agentMessages from "../tables/agentMessages.js";
import type * as tables_agentThreads from "../tables/agentThreads.js";
import type * as tables_comments from "../tables/comments.js";
import type * as tables_documents from "../tables/documents.js";
import type * as tables_locks from "../tables/locks.js";
import type * as tables_nodes from "../tables/nodes.js";
import type * as tables_projectMembers from "../tables/projectMembers.js";
import type * as tables_projects from "../tables/projects.js";
import type * as tables_reportVersions from "../tables/reportVersions.js";
import type * as tables_users from "../tables/users.js";

import type {
  ApiFromModules,
  FilterApi,
  FunctionReference,
} from "convex/server";

declare const fullApi: ApiFromModules<{
  debugAuth: typeof debugAuth;
  "features/agent": typeof features_agent;
  "features/locking": typeof features_locking;
  "tables/agentMessages": typeof tables_agentMessages;
  "tables/agentThreads": typeof tables_agentThreads;
  "tables/comments": typeof tables_comments;
  "tables/documents": typeof tables_documents;
  "tables/locks": typeof tables_locks;
  "tables/nodes": typeof tables_nodes;
  "tables/projectMembers": typeof tables_projectMembers;
  "tables/projects": typeof tables_projects;
  "tables/reportVersions": typeof tables_reportVersions;
  "tables/users": typeof tables_users;
}>;

/**
 * A utility for referencing Convex functions in your app's public API.
 *
 * Usage:
 * ```js
 * const myFunctionReference = api.myModule.myFunction;
 * ```
 */
export declare const api: FilterApi<
  typeof fullApi,
  FunctionReference<any, "public">
>;

/**
 * A utility for referencing Convex functions in your app's internal API.
 *
 * Usage:
 * ```js
 * const myFunctionReference = internal.myModule.myFunction;
 * ```
 */
export declare const internal: FilterApi<
  typeof fullApi,
  FunctionReference<any, "internal">
>;

export declare const components: {};
