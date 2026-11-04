/**
 * Step 1 of "Draw it": pick the land (geographic_setting).
 */

import type { GeographicSetting } from "../../../api/types";
import { ARCHETYPES, getArchetype } from "../archetypes";
import { CardRadioGroup, FlowColumns, StepHeading } from "../FlowLayout";
import { LandMiniMap, LandPlateArt } from "../illustrations";
import { FieldNote, Plate } from "../Plate";

const LAND_OPTIONS = ARCHETYPES.map((a) => a.value);

interface LandStepProps {
  land: GeographicSetting;
  onLandChange: (land: GeographicSetting) => void;
  placeName: string;
  /** Plate caption scale: the plate spans two districts. */
  districtSizeMeters: number;
}

export function LandStep({ land, onLandChange, placeName, districtSizeMeters }: LandStepProps) {
  const archetype = getArchetype(land);
  const title = "Where does your city begin?";

  return (
    <FlowColumns
      stepKey="land"
      left={
        <>
          <StepHeading title={title} aside="almost every great city starts at the water's edge…" />
          <CardRadioGroup
            label={title}
            options={LAND_OPTIONS}
            value={land}
            onChange={onLandChange}
            className="grid grid-cols-2 gap-3 min-[900px]:grid-cols-4"
            tilt={-1.5}
            padding={["gap-2 p-2", "gap-2 p-[7.5px]"]}
            optionLabel={(value) => {
              const a = getArchetype(value);
              return `${a.label}, like ${a.examples.join(", ")}`;
            }}
            renderCard={(value) => {
              const a = getArchetype(value);
              return (
                <>
                  <LandMiniMap id={value} className="block aspect-[121/78] max-h-24 w-full min-[900px]:max-h-none" />
                  <span className="font-display text-[16px] leading-5 font-semibold text-ink italic">{a.label}</span>
                  <span className="font-ui text-[12px] leading-4 text-body">{a.examples.join(" · ")}</span>
                </>
              );
            }}
          />
        </>
      }
      right={
        <>
          <Plate
            label={`Survey plate: ${archetype.label}`}
            caption={`PLATE I · ${((districtSizeMeters * 2) / 1000).toFixed(1)} KM ACROSS`}
          >
            <LandPlateArt land={land} placeName={placeName} />
          </Plate>
          <FieldNote title="Why here?" aside={`expect: ${archetype.expect}`} loose>
            {archetype.whyHere}
          </FieldNote>
        </>
      }
    />
  );
}
