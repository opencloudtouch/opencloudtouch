import { Link, useSearchParams } from "react-router";
import { useTranslation } from "react-i18next";
import { Icon } from "./Icon";
import "./BackToAbout.css";

/** Back link of the pages that belong to "About" (Diagnostics, Licenses). The target is /about; the selected device is kept like in the main navigation. */
export default function BackToAbout() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const device = searchParams.get("device") ?? searchParams.get("deviceId");
  const to = device ? `/about?device=${encodeURIComponent(device)}` : "/about";
  return (
    <Link to={to} className="pg-back">
      <span aria-hidden="true">{Icon.ArrowLeft(18)}</span>
      <span>{t("nav.about")}</span>
    </Link>
  );
}
