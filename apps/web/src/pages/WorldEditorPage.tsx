/**
 * World editor page - loads MapCanvas and EditorShell for a specific world.
 * This is lazy-loaded to avoid bundling PixiJS on the sign-in/sign-up pages.
 */

import { Link, useParams } from "react-router-dom";
import { MapCanvas } from "../components/canvas";
import { EditorShell } from "../components/shell";
import { CityLoader } from "../components/ui";
import { useWorld } from "../api";

export function WorldEditorPage() {
  const { worldId } = useParams<{ worldId: string }>();
  const { data: world, isLoading, error } = useWorld(worldId || "", {
    enabled: !!worldId,
    retry: 2,
    retryDelay: 1000,
  });

  if (!worldId) {
    return (
      <div className="p-8 text-red-600" data-testid="error">
        World ID not found
      </div>
    );
  }

  if (isLoading) {
    return <CityLoader variant="page" />;
  }

  if (error || !world) {
    return (
      <div className="p-8" data-testid="error">
        <h1 className="text-2xl font-bold text-red-600">World not found</h1>
        <p className="mt-2 text-gray-600">
          The world you're looking for doesn't exist or has been deleted.
        </p>
        <Link
          to="/"
          className="mt-4 inline-block text-blue-600 hover:underline"
        >
          Back to My Worlds
        </Link>
      </div>
    );
  }

  return (
    <EditorShell worldId={worldId}>
      <MapCanvas
        className="absolute inset-0"
        showMockFeatures={false}
        seed={world.seed}
        geographicSetting={world.settings?.geographic_setting}
        worldId={worldId}
      />
    </EditorShell>
  );
}
