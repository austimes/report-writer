import { useQuery, useMutation } from 'convex/react';
import { api } from '@/lib/convex';
import type { Id } from 'convex/_generated/dataModel';

export function useAgentThread(threadId: Id<'agentThreads'>) {
  const thread = useQuery(api.tables.agentThreads.getById, { id: threadId });
  const messages = useQuery(api.tables.agentMessages.listByThread, { threadId });
  const sendMessage = useMutation(api.features.agent.runAgentOnThread);
  const forkThread = useMutation(api.features.agent.forkThread);

  const send = async (userMessage: string) => {
    await sendMessage({ threadId, userMessage });
  };

  const fork = async (title?: string) => {
    return await forkThread({ parentThreadId: threadId, title });
  };

  return {
    thread,
    messages,
    sendMessage: send,
    forkThread: fork,
  };
}
