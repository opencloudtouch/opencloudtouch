import { useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { motion, AnimatePresence, PanInfo, useIsPresent } from "framer-motion";
import { useTranslation } from "react-i18next";
import type { Device } from "../api/devices";
import { Icon } from "./Icon";
import "./DeviceSwiper.css";

export type { Device } from "../api/devices";

interface DeviceSwiperProps {
  devices: Device[];
  currentIndex: number;
  onIndexChange: (index: number) => void;
  children: ReactNode;
}

/* ---- dots: one row at any device count -------------------------------------------------------
   full   : count * 44 px fits            -> 44 px targets (as before)
   dense  : count * 24 px fits            -> targets shrink to width/count (24..44 px wide, 44 px high), the visible dot shrinks with them
   window : even 24 px per dot does not fit -> only the dots around the current device are shown (current one centred,
            the outer dots on a side with more devices are small); every shown dot keeps >= 24 px (WCAG 2.2 SC 2.5.8)
   The arrows (44 px) always reach every device, so no function depends on a small target. */
const DOT_FULL = 44;
const DOT_MIN = 24;

type DotDensity = "full" | "dense" | "window";

function getDotLayout(
  count: number,
  width: number
): { density: DotDensity; visible: number; pitch: number } {
  if (!width || count * DOT_FULL <= width)
    return { density: "full", visible: count, pitch: DOT_FULL };
  if (count * DOT_MIN <= width) {
    return {
      density: "dense",
      visible: count,
      pitch: Math.floor((width / count) * 10) / 10,
    };
  }
  const visible = Math.max(3, Math.floor(width / DOT_MIN));
  return { density: "window", visible, pitch: Math.floor((width / visible) * 10) / 10 };
}

/* ---- motion spec: crossfade, both cards overlap (popLayout), never an empty frame ----
   About 340 ms in total (between the old 500 ms and the 190 ms of the first design). Opacity is linear and
   equally long on both cards, so the combined cover never drops below 75 %. Tune here. */
const ENTER_X = 24; // px, the new card slides in from the side it comes from
const EXIT_X = 12; // px, the old card moves away a shorter distance
const ENTER_X_S = 0.32;
const FADE_S = 0.24;
const EXIT_X_S = 0.24;

/** While the old card fades out (both cards are in the DOM) it is hidden from assistive technology and not operable. */
function CardShell({ children }: Readonly<{ children: ReactNode }>) {
  const isPresent = useIsPresent(); // not usePresence(): that would make this component responsible for calling safeToRemove, and the old card would never be removed
  return (
    <div
      className="ds-card-shell"
      aria-hidden={isPresent ? undefined : true}
      inert={!isPresent}
      data-state={isPresent ? "current" : "leaving"}
    >
      {children}
    </div>
  );
}

export default function DeviceSwiper({
  devices,
  currentIndex,
  onIndexChange,
  children,
}: DeviceSwiperProps) {
  const { t } = useTranslation();
  const [dragDirection, setDragDirection] = useState(0);
  const dotsRef = useRef<HTMLDivElement>(null);
  const [dotsWidth, setDotsWidth] = useState(0);

  useLayoutEffect(() => {
    const el = dotsRef.current;
    if (!el) return;
    const measure = () => setDotsWidth(el.clientWidth);
    measure();
    if (typeof ResizeObserver === "undefined") return; // jsdom: stays on the full layout
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const handleDragEnd = (_event: MouseEvent | TouchEvent | PointerEvent, info: PanInfo) => {
    const swipeThreshold = 50;
    const swipeVelocity = 500;

    if (info.offset.x > swipeThreshold || info.velocity.x > swipeVelocity) {
      // Swipe right - previous device
      if (currentIndex > 0) {
        onIndexChange(currentIndex - 1);
        setDragDirection(-1);
      }
    } else if (info.offset.x < -swipeThreshold || info.velocity.x < -swipeVelocity) {
      // Swipe left - next device
      if (currentIndex < devices.length - 1) {
        onIndexChange(currentIndex + 1);
        setDragDirection(1);
      }
    }
  };

  const goToPrevious = () => {
    if (currentIndex > 0) {
      onIndexChange(currentIndex - 1);
      setDragDirection(-1);
    }
  };

  const goToNext = () => {
    if (currentIndex < devices.length - 1) {
      onIndexChange(currentIndex + 1);
      setDragDirection(1);
    }
  };

  const variants = {
    enter: (direction: number) => ({
      x: direction > 0 ? ENTER_X : -ENTER_X,
      opacity: 0,
    }),
    center: {
      x: 0,
      opacity: 1,
      transition: {
        x: { duration: ENTER_X_S, ease: [0.33, 1, 0.68, 1] as const }, // ease-out cubic: no long crawl in the last pixels
        opacity: { duration: FADE_S, ease: "linear" as const },
      },
    },
    exit: (direction: number) => ({
      x: direction < 0 ? EXIT_X : -EXIT_X,
      opacity: 0,
      transition: {
        x: { duration: EXIT_X_S, ease: [0.4, 0, 1, 1] as const },
        opacity: { duration: FADE_S, ease: "linear" as const },
      },
    }),
  };

  const count = devices.length;
  const { density, visible, pitch } = getDotLayout(count, dotsWidth);
  const start =
    density === "window"
      ? Math.min(Math.max(currentIndex - Math.floor(visible / 2), 0), count - visible)
      : 0;
  const shown = devices.slice(start, start + visible);

  return (
    <div className="ds" data-test="device-swiper">
      {/* Navigation Arrows (desktop: left/right of the card; phones <= 480px: in the dots row) */}
      <button
        className="ds-arrow ds-arrow--prev"
        onClick={goToPrevious}
        disabled={currentIndex === 0}
        aria-label={t("player.prevDevice")}
        data-test="device-prev"
      >
        {Icon.ChevronLeft(24)}
      </button>

      <button
        className="ds-arrow ds-arrow--next"
        onClick={goToNext}
        disabled={currentIndex === devices.length - 1}
        aria-label={t("player.nextDevice")}
        data-test="device-next"
      >
        {Icon.ChevronRight(24)}
      </button>

      {/* Swipeable Card Container */}
      <div className="ds-viewport">
        <AnimatePresence initial={false} custom={dragDirection} mode="popLayout">
          <motion.div
            key={currentIndex}
            custom={dragDirection}
            variants={variants}
            initial="enter"
            animate="center"
            exit="exit"
            drag={false}
            dragConstraints={{ left: 0, right: 0 }}
            dragElastic={0.2}
            onDragEnd={handleDragEnd}
            className="ds-card"
          >
            <CardShell>{children}</CardShell>
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Device picker: group of buttons, current one has aria-current (no tab pattern: there is no tab panel) */}
      <div
        ref={dotsRef}
        className={`ds-dots ds-dots--${density}`}
        role="group"
        aria-label={t("a11y.deviceSelection")}
        style={{ "--ds-pitch": `${pitch}px` } as CSSProperties}
      >
        {shown.map((device, offset) => {
          const index = start + offset;
          const edge =
            density === "window" &&
            ((offset === 0 && start > 0) || (offset === visible - 1 && start + visible < count));
          return (
            <button
              key={device.device_id}
              className={`ds-dot${index === currentIndex ? " ds-dot--active" : ""}${edge ? " ds-dot--edge" : ""}`}
              onClick={() => {
                setDragDirection(index > currentIndex ? 1 : -1);
                onIndexChange(index);
              }}
              aria-current={index === currentIndex ? "true" : undefined}
              aria-label={t("a11y.switchToDevice", { name: device.name })}
              title={device.name}
            />
          );
        })}
        {density === "window" && (
          <span className="visually-hidden" role="status">
            {t("a11y.deviceCounter", { current: currentIndex + 1, total: count })}
          </span>
        )}
      </div>
    </div>
  );
}
