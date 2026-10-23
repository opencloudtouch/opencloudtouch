import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import { motion, AnimatePresence, PanInfo, useIsPresent, useReducedMotion } from "framer-motion";
import { useTranslation } from "react-i18next";
import type { Device } from "../api/devices";
import { Icon } from "./Icon";
import "./DeviceSwiper.css";
import "./DeviceSwiper.sticky.css";

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

/* ---- swipe (touch and pen only): the card follows the finger, release past a distance or a flick switches ---- */
const SWIPE_LOCK = 10; // px of movement before the direction is decided
const SWIPE_DIST_MAX = 80; // px, switch distance is min(this, 25 % of the card width)
const SWIPE_DIST_FRAC = 0.25;
const SWIPE_FLICK_MIN = 24; // px and
const SWIPE_FLICK_V = 0.4; // px/ms: a flick switches
const EDGE_MAX = 32; // px, rubber band at the first / last device
const EDGE_K = 120;
/* a gesture that starts on one of these is not a swipe (volume slider, name editor, marquee title) */
const NO_SWIPE = '.vs-track,[role="slider"],input,textarea,select,.dne,.dne-btn,.np-marquee';

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
    const measure = () => {
      if (el.clientWidth > 0) setDotsWidth(el.clientWidth); // 0 = dots hidden (sticky bar): keep the last width
    };
    measure();
    if (typeof ResizeObserver === "undefined") return; // jsdom: stays on the full layout
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const reduce = useReducedMotion();
  const dsRef = useRef<HTMLDivElement>(null);
  const swipeRef = useRef<{
    card: HTMLElement | null;
    ok: boolean;
    lock: "" | "x" | "y";
    dx: number;
    moved: boolean;
  }>({ card: null, ok: false, lock: "", dx: 0, moved: false });
  const count = devices.length;

  const cue = (dx: number, armed: boolean) => {
    const el = dsRef.current;
    if (!el) return;
    if (dx) el.dataset.pull = dx < 0 ? "next" : "prev";
    else delete el.dataset.pull;
    if (armed) el.dataset.armed = "";
    else delete el.dataset.armed;
  };
  const threshold = () =>
    Math.min(SWIPE_DIST_MAX, (swipeRef.current.card?.clientWidth || 320) * SWIPE_DIST_FRAC);

  const onPointerDownCapture = (e: React.PointerEvent<HTMLElement>) => {
    const s = swipeRef.current;
    s.card = e.currentTarget;
    s.lock = "";
    s.dx = 0;
    s.moved = false;
    s.ok =
      e.pointerType !== "mouse" && !(e.target instanceof Element && e.target.closest(NO_SWIPE));
  };
  const onPan = (_e: PointerEvent, info: PanInfo) => {
    const s = swipeRef.current;
    if (!s.ok || !s.card) return;
    const { x: dx, y: dy } = info.offset;
    if (!s.lock) {
      if (Math.abs(dx) < SWIPE_LOCK && Math.abs(dy) < SWIPE_LOCK) return;
      s.lock = Math.abs(dx) >= Math.abs(dy) * 1.2 ? "x" : "y";
      if (s.lock === "x") s.card.dataset.dragging = "";
    }
    if (s.lock !== "x") return;
    s.dx = dx;
    s.moved = true;
    const edge = (dx > 0 && currentIndex === 0) || (dx < 0 && currentIndex === count - 1);
    if (!reduce) {
      const x = edge ? Math.sign(dx) * EDGE_MAX * (1 - Math.exp(-Math.abs(dx) / EDGE_K)) : dx;
      s.card.style.setProperty("--ds-x", `${x}px`);
    }
    cue(dx, !edge && Math.abs(dx) >= threshold());
  };
  const onPanEnd = (_e: PointerEvent, info: PanInfo) => {
    const s = swipeRef.current;
    const card = s.card;
    if (!card || s.lock !== "x") return;
    card.removeAttribute("data-dragging");
    cue(0, false);
    const dx = info.offset.x;
    const v = info.velocity.x / 1000; // px/ms
    const dir = dx < 0 ? 1 : -1;
    const can = dir > 0 ? currentIndex < count - 1 : currentIndex > 0;
    const flick =
      Math.abs(dx) >= SWIPE_FLICK_MIN &&
      Math.abs(v) >= SWIPE_FLICK_V &&
      Math.sign(v) === Math.sign(dx);
    if (can && (Math.abs(dx) >= threshold() || flick)) {
      setDragDirection(dir);
      onIndexChange(currentIndex + dir);
    } else if (!reduce) {
      card.dataset.settle = "";
      card.style.setProperty("--ds-x", "0px");
      window.setTimeout(() => card.removeAttribute("data-settle"), 260);
    }
    window.setTimeout(() => {
      s.moved = false;
    }, 0);
  };

  // Sticky bar: "stuck" while the bar sits at the top edge of the scrolling <main> with content running underneath it
  const barRef = useRef<HTMLDivElement>(null);
  const [stuck, setStuck] = useState(false);
  useEffect(() => {
    const el = barRef.current;
    const root = el?.closest("main");
    if (!el || !root || typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver(
      (entries) => {
        const e = entries[0];
        if (!e) return;
        setStuck(
          e.intersectionRatio < 1 && e.boundingClientRect.top <= (e.rootBounds?.top ?? 0) + 1
        );
      },
      { root, rootMargin: "-1px 0px 0px 0px", threshold: [1] }
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

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
      pointerEvents: "none" as const, // the leaving card never swallows a tap
      transition: {
        x: { duration: EXIT_X_S, ease: [0.4, 0, 1, 1] as const },
        opacity: { duration: FADE_S, ease: "linear" as const },
      },
    }),
  };

  const { density, visible, pitch } = getDotLayout(count, dotsWidth);
  const start =
    density === "window"
      ? Math.min(Math.max(currentIndex - Math.floor(visible / 2), 0), count - visible)
      : 0;
  const shown = devices.slice(start, start + visible);

  return (
    <div
      className="ds"
      ref={dsRef}
      data-test="device-swiper"
      data-prev={currentIndex > 0 || undefined}
      data-next={currentIndex < count - 1 || undefined}
    >
      {/* Switch bar: arrows + dots (+ name while stuck). Desktop: arrows left/right of the card, phones: one bar above it */}
      <div className="ds-bar" ref={barRef} data-stuck={stuck || undefined}>
        <button
          className="ds-arrow ds-arrow--prev"
          onClick={goToPrevious}
          disabled={currentIndex === 0}
          aria-label={t("player.prevDevice")}
          data-test="device-prev"
        >
          {Icon.ChevronLeft(24)}
        </button>

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
        <span className="ds-bar-name" aria-hidden="true">
          {devices[currentIndex]?.name} · {currentIndex + 1}/{count}
        </span>
        <button
          className="ds-arrow ds-arrow--next"
          onClick={goToNext}
          disabled={currentIndex === devices.length - 1}
          aria-label={t("player.nextDevice")}
          data-test="device-next"
        >
          {Icon.ChevronRight(24)}
        </button>
      </div>

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
            onPointerDownCapture={onPointerDownCapture}
            onPan={onPan}
            onPanEnd={onPanEnd}
            onClickCapture={(e) => {
              if (swipeRef.current.moved) {
                e.preventDefault();
                e.stopPropagation(); // a swipe that ends on a button must not click it
              }
            }}
            className="ds-card"
          >
            <CardShell>{children}</CardShell>
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
