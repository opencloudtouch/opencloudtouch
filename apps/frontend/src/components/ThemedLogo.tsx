import "./ThemedLogo.css";

const DARK_SRC = "/images/logo/oct-logo-dark_539x539.png"; // white strokes, for dark backgrounds
const LIGHT_SRC = "/images/logo/oct-logo-light_583x583.png"; // dark strokes, for light backgrounds

interface Props {
  size: number;
  alt: string;
  className?: string;
}

/** Both images are rendered; CSS shows the one that fits the active theme. */
export default function ThemedLogo({ size, alt, className = "" }: Readonly<Props>) {
  const common = { alt, width: size, height: size, loading: "lazy" as const };
  return (
    <>
      <img
        {...common}
        className={`${className} themed-logo themed-logo--for-dark`.trim()}
        src={DARK_SRC}
      />
      <img
        {...common}
        className={`${className} themed-logo themed-logo--for-light`.trim()}
        src={LIGHT_SRC}
      />
    </>
  );
}
