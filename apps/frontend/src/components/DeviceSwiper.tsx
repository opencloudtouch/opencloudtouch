import { useState, ReactNode } from "react";
import { motion, AnimatePresence, PanInfo } from "framer-motion";
import { useTranslation } from "react-i18next";
import type { Device } from "../api/devices";
import "./DeviceSwiper.css";

export type { Device } from "../api/devices";

interface DeviceSwiperProps {
  devices: Device[];
  currentIndex: number;
  onIndexChange: (index: number) => void;
  children: ReactNode;
}

export default function DeviceSwiper({
  devices,
  currentIndex,
  onIndexChange,
  children,
}: DeviceSwiperProps) {
  const { t } = useTranslation();
  const [dragDirection, setDragDirection] = useState(0);

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
      x: direction > 0 ? 1000 : -1000,
      opacity: 0,
      scale: 0.8,
    }),
    center: {
      x: 0,
      opacity: 1,
      scale: 1,
    },
    exit: (direction: number) => ({
      x: direction < 0 ? 1000 : -1000,
      opacity: 0,
      scale: 0.8,
    }),
  };

  return (
    <div className="device-swiper" data-test="device-swiper">
      {/* Navigation Arrows */}
      <button
        className="swipe-arrow swipe-arrow-left"
        onClick={goToPrevious}
        disabled={currentIndex === 0}
        aria-label={t("player.prevDevice")}
        data-test="device-prev"
      >
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <polyline points="15 18 9 12 15 6" />
        </svg>
      </button>

      <button
        className="swipe-arrow swipe-arrow-right"
        onClick={goToNext}
        disabled={currentIndex === devices.length - 1}
        aria-label={t("player.nextDevice")}
        data-test="device-next"
      >
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <polyline points="9 18 15 12 9 6" />
        </svg>
      </button>

      {/* Swipeable Card Container */}
      <div className="swiper-container">
        <AnimatePresence initial={false} custom={dragDirection} mode="wait">
          <motion.div
            key={currentIndex}
            custom={dragDirection}
            variants={variants}
            initial="enter"
            animate="center"
            exit="exit"
            transition={{
              x: { type: "spring", stiffness: 300, damping: 30 },
              opacity: { duration: 0.2 },
              scale: { duration: 0.2 },
            }}
            drag={false}
            dragConstraints={{ left: 0, right: 0 }}
            dragElastic={0.2}
            onDragEnd={handleDragEnd}
            className="swiper-card"
          >
            {children}
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Dots Indicator */}
      <div className="swiper-dots" role="tablist" aria-label="Device selection">
        {devices.map((device, index) => (
          <button
            key={device.device_id}
            className={`dot ${index === currentIndex ? "active" : ""}`}
            onClick={() => {
              setDragDirection(index > currentIndex ? 1 : -1);
              onIndexChange(index);
            }}
            role="tab"
            aria-selected={index === currentIndex}
            aria-label={`Switch to ${device.name}`}
          />
        ))}
      </div>
    </div>
  );
}
