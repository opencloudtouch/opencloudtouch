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
      className={`skeleton ${className}`}
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
    <div className="device-card-skeleton">
      <Skeleton width="60px" height="60px" borderRadius="50%" />
      <div className="device-card-skeleton-content">
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
    <div className="preset-skeleton">
      <Skeleton width="48px" height="48px" borderRadius="8px" />
      <div className="preset-skeleton-content">
        <Skeleton width="80%" height="18px" />
        <Skeleton width="60%" height="14px" />
      </div>
    </div>
  );
}

/**
 * Station card skeleton for radio search results
 */
export function StationCardSkeleton() {
  return (
    <div className="station-card-skeleton">
      <Skeleton width="100%" height="120px" borderRadius="8px" />
      <div className="station-card-skeleton-content">
        <Skeleton width="90%" height="20px" />
        <Skeleton width="70%" height="16px" />
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
        <SkeletonComponent key={index} />
      ))}
    </>
  );
}
