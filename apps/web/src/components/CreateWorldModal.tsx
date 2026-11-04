/**
 * Modal for creating a new world.
 *
 * CITY-658: replaced the flat form with the 3-step "Found a city" flow.
 * Kept as a thin wrapper so callers (WorldsPage) don't change.
 */

import { FoundCityModal } from "./found-city/FoundCityModal";

interface CreateWorldModalProps {
  onClose: () => void;
  onCreated: (worldId: string) => void;
}

export function CreateWorldModal({ onClose, onCreated }: CreateWorldModalProps) {
  return <FoundCityModal onClose={onClose} onCreated={onCreated} />;
}
