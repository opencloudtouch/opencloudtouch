/**
 * Loading Skeleton Components
 * Visual placeholders for content that is loading
 */
import "./LoadingSkeleton.css";

interface SkeletonProps {
  width?: string;
  height?: string;
  borderRadius?: string;
  className?: string;
}

/**
 * Generic skeleton placeholder
 */
export function Skeleton({
  width = "100%",
  height = "20px",
  borderRadius = "4px",
  className = "",
}: SkeletonProps) {
  return (
    <div
      className={`ui-skeleton ${className}`}
      style={{
        width,
        height,
        borderRadius,
      }}
      aria-hidden="true"
    />
  );
}

/**
 * Device card skeleton for device list loading state
 */
export function DeviceCardSkeleton() {
  return (
    <div className="sk-device">
      <Skeleton width="60px" height="60px" borderRadius="50%" />
      <div className="sk-content">
        <Skeleton width="70%" height="24px" />
        <Skeleton width="40%" height="16px" />
      </div>
    </div>
  );
}

/**
 * Preset slot skeleton for loading preset states
 */
export function PresetSkeleton() {
  return (
    <div className="sk-preset">
      <Skeleton width="28px" height="28px" borderRadius="50%" />
      <Skeleton width="40px" height="40px" borderRadius="8px" />
      <div className="sk-content">
        <Skeleton width="80%" height="18px" />
      </div>
    </div>
  );
}

/**
 * Station card skeleton for radio search results
 */
export function StationCardSkeleton() {
  return (
    <div className="sk-station">
      <Skeleton width="40px" height="40px" borderRadius="8px" />
      <div className="sk-content">
        <Skeleton width="70%" height="18px" />
        <Skeleton width="40%" height="14px" />
      </div>
    </div>
  );
}

/**
 * List of skeleton items (generic)
 */
interface SkeletonListProps {
  count: number;
  SkeletonComponent: React.ComponentType;
}

export function SkeletonList({ count, SkeletonComponent }: SkeletonListProps) {
  return (
    <>
      {Array.from({ length: count }).map((_, index) => (
        // eslint-disable-next-line @eslint-react/no-array-index-key -- no stable key for generated skeleton placeholders
        <SkeletonComponent key={index} />
      ))}
    </>
  );
}
