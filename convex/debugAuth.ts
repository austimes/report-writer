import { query } from "./_generated/server";

export const getAuthStatus = query({
  args: {},
  handler: async (ctx) => {
    const identity = await ctx.auth.getUserIdentity();
    
    if (!identity) {
      console.warn("[Convex debugAuth] No identity");
      return { hasIdentity: false };
    }

    console.log("[Convex debugAuth] identity", {
      subject: identity.subject,
      issuer: identity.issuer,
      tokenIdentifier: identity.tokenIdentifier,
    });

    return {
      hasIdentity: true,
      subject: identity.subject,
      issuer: identity.issuer,
      tokenIdentifier: identity.tokenIdentifier,
    };
  },
});
