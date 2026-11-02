import { Link } from "react-router";
import { useTranslation } from "react-i18next";
import { Icon } from "./Icon";
import "./BackToAbout.css";

/** Back link of the pages that belong to "About" (Diagnostics, Licenses). The target is always /about. */
export default function BackToAbout() {
  const { t } = useTranslation();
  return (
    <Link to="/about" className="pg-back">
      <span aria-hidden="true">{Icon.ArrowLeft(18)}</span>
      <span>{t("nav.about")}</span>
    </Link>
  );
}
