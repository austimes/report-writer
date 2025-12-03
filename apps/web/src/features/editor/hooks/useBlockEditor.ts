import { useCallback, useRef, useState } from "react";
import { useMutation } from "convex/react";
import { api } from "../../../lib/convex";
import type { Id } from "convex/_generated/dataModel";

export function useBlockEditor(userId: Id<"users"> | null) {
  const updateTextMutation = useMutation(api.tables.nodes.updateText);
  const [saving, setSaving] = useState(false);
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout>>();

  const saveNode = useCallback(
    async (nodeId: Id<"nodes">, text: string) => {
      if (!userId) return;
      
      setSaving(true);
      try {
        await updateTextMutation({
          id: nodeId,
          text,
          editorUserId: userId,
          editType: "human",
        });
      } finally {
        setSaving(false);
      }
    },
    [userId, updateTextMutation]
  );

  const debouncedSave = useCallback(
    (nodeId: Id<"nodes">, text: string, delay = 500) => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }

      saveTimeoutRef.current = setTimeout(() => {
        saveNode(nodeId, text);
      }, delay);
    },
    [saveNode]
  );

  const immediateSave = useCallback(
    (nodeId: Id<"nodes">, text: string) => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
      saveNode(nodeId, text);
    },
    [saveNode]
  );

  return {
    debouncedSave,
    immediateSave,
    saving,
  };
}
