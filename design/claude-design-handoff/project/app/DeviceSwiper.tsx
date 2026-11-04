import { useState, ReactNode } from "react";
import { motion, AnimatePresence, PanInfo } from "framer-motion";
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
            className="ds-card"
          >
            {children}
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Device picker: group of buttons, current one has aria-current (no tab pattern: there is no tab panel) */}
      <div className="ds-dots" role="group" aria-label={t("a11y.deviceSelection")}>
        {devices.map((device, index) => (
          <button
            key={device.device_id}
            className={`ds-dot${index === currentIndex ? " ds-dot--active" : ""}`}
            onClick={() => {
              setDragDirection(index > currentIndex ? 1 : -1);
              onIndexChange(index);
            }}
            aria-current={index === currentIndex ? "true" : undefined}
            aria-label={t("a11y.switchToDevice", { name: device.name })}
            title={device.name}
          />
        ))}
      </div>
    </div>
  );
}
