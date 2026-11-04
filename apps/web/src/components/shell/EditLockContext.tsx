import {
  createContext,
  useContext,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  ReactNode,
} from "react";
import {
  useCreateTile,
  useAcquireLock,
  useReleaseLock,
  useHeartbeatLock,
} from "../../api/hooks";
import { ApiClientError } from "../../api/types";
import { getLastAuthToken } from "../../api/client";

interface LockConflict {
  lockedBy: string;
  expiresAt: string;
}

interface EditLockContextValue {
  isEditing: boolean;
  isAcquiring: boolean;
  lockConflict: LockConflict | null;
  requestEditMode: () => void;
  exitEditMode: () => void;
  dismissConflict: () => void;
}

const EditLockContext = createContext<EditLockContextValue | null>(null);

interface EditLockProviderProps {
  children: ReactNode;
  worldId?: string;
}

const LOCK_DURATION_SECONDS = 300;
const HEARTBEAT_INTERVAL_MS = 120_000;

export function EditLockProvider({ children, worldId }: EditLockProviderProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [isAcquiring, setIsAcquiring] = useState(false);
  const [lockConflict, setLockConflict] = useState<LockConflict | null>(null);
  const [sentinelTileId, setSentinelTileId] = useState<string | null>(null);
  const heartbeatRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const sentinelTileIdRef = useRef<string | null>(null);

  // Keep ref in sync for cleanup callbacks
  useEffect(() => {
    sentinelTileIdRef.current = sentinelTileId;
  }, [sentinelTileId]);

  const createTile = useCreateTile();
  const acquireLock = useAcquireLock();
  const releaseLock = useReleaseLock();
  const heartbeatLock = useHeartbeatLock();

  // Ensure sentinel tile exists on mount
  useEffect(() => {
    if (!worldId) return;
    createTile.mutate(
      { world_id: worldId, tx: 1, ty: 1 },
      {
        onSuccess: (tile) => {
          setSentinelTileId(tile.id);
        },
      }
    );
    // Only run when worldId changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [worldId]);

  const clearHeartbeat = useCallback(() => {
    if (heartbeatRef.current) {
      clearInterval(heartbeatRef.current);
      heartbeatRef.current = null;
    }
  }, []);

  const startHeartbeat = useCallback(
    (tileId: string) => {
      clearHeartbeat();
      heartbeatRef.current = setInterval(() => {
        heartbeatLock.mutate({
          tileId,
          durationSeconds: LOCK_DURATION_SECONDS,
        });
      }, HEARTBEAT_INTERVAL_MS);
    },
    [clearHeartbeat, heartbeatLock]
  );

  const requestEditMode = useCallback(() => {
    if (!sentinelTileId || isAcquiring || isEditing) return;

    setIsAcquiring(true);
    setLockConflict(null);

    acquireLock.mutate(
      {
        tileId: sentinelTileId,
        data: { duration_seconds: LOCK_DURATION_SECONDS },
      },
      {
        onSuccess: () => {
          setIsEditing(true);
          setIsAcquiring(false);
          startHeartbeat(sentinelTileId);
        },
        onError: (error) => {
          setIsAcquiring(false);
          if (error instanceof ApiClientError && error.status === 409) {
            // Parse lock conflict info from error detail
            const detail = error.detail as
              | { detail?: { locked_by?: string; expires_at?: string } }
              | undefined;
            const info = detail?.detail;
            setLockConflict({
              lockedBy: info?.locked_by ?? "another user",
              expiresAt: info?.expires_at ?? "",
            });
          }
        },
      }
    );
  }, [sentinelTileId, isAcquiring, isEditing, acquireLock, startHeartbeat]);

  const exitEditMode = useCallback(() => {
    if (!sentinelTileId) return;

    clearHeartbeat();
    setIsEditing(false);

    releaseLock.mutate(sentinelTileId);
  }, [sentinelTileId, clearHeartbeat, releaseLock]);

  const dismissConflict = useCallback(() => {
    setLockConflict(null);
  }, []);

  // Auto-enter edit mode once the sentinel tile is ready
  useEffect(() => {
    if (sentinelTileId && !isEditing && !isAcquiring) {
      requestEditMode();
    }
    // Only trigger when sentinelTileId becomes available
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sentinelTileId]);

  // Release lock on unmount
  useEffect(() => {
    return () => {
      clearHeartbeat();
      const tileId = sentinelTileIdRef.current;
      if (tileId) {
        // Fire-and-forget release
        import("../../api/client").then((client) => {
          client.tiles.releaseLock(tileId).catch(() => {});
        });
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Release lock on beforeunload
  useEffect(() => {
    const handleBeforeUnload = () => {
      const tileId = sentinelTileIdRef.current;
      if (!tileId) return;

      // Use sendBeacon or fetch with keepalive for reliable delivery
      const url = `${
        import.meta.env.VITE_API_URL || "http://localhost:8000"
      }/tiles/${tileId}/lock`;
      // beforeunload can't await Clerk's getToken; use the last token the API
      // client fetched (best-effort — the lock also expires on its own).
      const token = getLastAuthToken();

      try {
        fetch(url, {
          method: "DELETE",
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          keepalive: true,
        });
      } catch {
        // Best-effort
      }
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, []);

  const value: EditLockContextValue = useMemo(
    () => ({
      isEditing,
      isAcquiring,
      lockConflict,
      requestEditMode,
      exitEditMode,
      dismissConflict,
    }),
    [isEditing, isAcquiring, lockConflict, requestEditMode, exitEditMode, dismissConflict]
  );

  return (
    <EditLockContext.Provider value={value}>
      {children}
    </EditLockContext.Provider>
  );
}

export function useEditLock(): EditLockContextValue {
  const context = useContext(EditLockContext);
  if (!context) {
    throw new Error("useEditLock must be used within an EditLockProvider");
  }
  return context;
}

export function useEditLockOptional(): EditLockContextValue | null {
  return useContext(EditLockContext);
}
