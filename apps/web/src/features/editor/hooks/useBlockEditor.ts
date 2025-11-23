import { useCallback, useRef, useState } from "react";
import { useMutation } from "convex/react";
import { api } from "../../../lib/convex";
import type { Id } from "convex/_generated/dataModel";

export function useBlockEditor(userId: Id<"users"> | null) {
  const updateTextMutation = useMutation(api.tables.blocks.updateText);
  const [saving, setSaving] = useState(false);
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout>>();

  const saveBlock = useCallback(
    async (blockId: Id<"blocks">, markdownText: string) => {
      if (!userId) return;
      
      setSaving(true);
      try {
        await updateTextMutation({
          id: blockId,
          markdownText,
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
    (blockId: Id<"blocks">, markdownText: string, delay = 500) => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }

      saveTimeoutRef.current = setTimeout(() => {
        saveBlock(blockId, markdownText);
      }, delay);
    },
    [saveBlock]
  );

  const immediateSave = useCallback(
    (blockId: Id<"blocks">, markdownText: string) => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
      saveBlock(blockId, markdownText);
    },
    [saveBlock]
  );

  return {
    debouncedSave,
    immediateSave,
    saving,
  };
}
