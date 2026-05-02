import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import LanguageSelector from "../../src/components/LanguageSelector";
import * as i18nModule from "../../src/i18n";

vi.mock("../../src/i18n", async (importOriginal) => {
  const actual = await importOriginal<typeof i18nModule>();
  return {
    ...actual,
    changeLanguage: vi.fn(),
  };
});

// Mock i18next instance used by useTranslation
vi.mock("react-i18next", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    useTranslation: () => ({
      t: (key: string) => key,
      i18n: { language: "en" },
    }),
  };
});

describe("LanguageSelector", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders flag and 2-letter code of current language", () => {
    render(<LanguageSelector />);
    // The button should contain the flag and code
    expect(screen.getByRole("button", { name: /language|select language/i })).toBeInTheDocument();
    // EN code or flag visible
    const button = screen.getByRole("button", { name: /language|select language/i });
    expect(button.textContent).toMatch(/EN|🇬🇧/);
  });

  it("opens dropdown on click", () => {
    render(<LanguageSelector />);
    const button = screen.getByRole("button", { name: /language|select language/i });

    // Dropdown not visible initially
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();

    fireEvent.click(button);
    expect(screen.getByRole("listbox")).toBeInTheDocument();
  });

  it("shows all supported locales in dropdown", () => {
    render(<LanguageSelector />);
    fireEvent.click(screen.getByRole("button", { name: /language|select language/i }));

    const options = screen.getAllByRole("option");
    expect(options.length).toBe(10); // en, de, fr, it, es, nl, pt-BR, ja, pl, sv
  });

  it("shows checkmark on active locale option", () => {
    render(<LanguageSelector />);
    fireEvent.click(screen.getByRole("button", { name: /language|select language/i }));

    // Active option (en) should have aria-selected="true"
    const activeOption = screen.getAllByRole("option").find(
      (o) => o.getAttribute("aria-selected") === "true"
    );
    expect(activeOption).toBeDefined();
  });

  it("calls changeLanguage and closes dropdown on locale select", () => {
    render(<LanguageSelector />);
    fireEvent.click(screen.getByRole("button", { name: /language|select language/i }));

    const options = screen.getAllByRole("option");
    const frOption = options.find((o) => o.textContent?.includes("FR") || o.textContent?.includes("Français"));
    expect(frOption).toBeDefined();
    fireEvent.click(frOption!);

    expect(i18nModule.changeLanguage).toHaveBeenCalledWith("fr");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("closes dropdown on Escape key", () => {
    render(<LanguageSelector />);
    fireEvent.click(screen.getByRole("button", { name: /language|select language/i }));
    expect(screen.getByRole("listbox")).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("closes dropdown on outside click", () => {
    render(
      <div>
        <LanguageSelector />
        <div data-testid="outside">outside</div>
      </div>
    );
    fireEvent.click(screen.getByRole("button", { name: /language|select language/i }));
    expect(screen.getByRole("listbox")).toBeInTheDocument();

    fireEvent.mouseDown(screen.getByTestId("outside"));
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("has aria-label on the toggle button", () => {
    render(<LanguageSelector />);
    const button = screen.getByRole("button", { name: /language|select language/i });
    expect(button).toHaveAttribute("aria-label");
  });

  it("sets aria-expanded on toggle button", () => {
    render(<LanguageSelector />);
    const button = screen.getByRole("button", { name: /language|select language/i });
    expect(button).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
  });

  it("listbox has role='listbox'", () => {
    render(<LanguageSelector />);
    fireEvent.click(screen.getByRole("button", { name: /language|select language/i }));
    expect(screen.getByRole("listbox")).toBeInTheDocument();
  });

  it("options have role='option' and aria-selected", () => {
    render(<LanguageSelector />);
    fireEvent.click(screen.getByRole("button", { name: /language|select language/i }));
    const options = screen.getAllByRole("option");
    expect(options.length).toBeGreaterThan(0);
    for (const option of options) {
      expect(option).toHaveAttribute("aria-selected");
    }
  });

  it("selects locale on Enter key press and closes dropdown", () => {
    render(<LanguageSelector />);
    fireEvent.click(screen.getByRole("button", { name: /language|select language/i }));

    const options = screen.getAllByRole("option");
    const deOption = options.find(
      (o) => o.textContent?.includes("DE") || o.textContent?.includes("Deutsch")
    );
    expect(deOption).toBeDefined();
    fireEvent.keyDown(deOption!, { key: "Enter" });

    expect(i18nModule.changeLanguage).toHaveBeenCalledWith("de");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("selects locale on Space key press and closes dropdown", () => {
    render(<LanguageSelector />);
    fireEvent.click(screen.getByRole("button", { name: /language|select language/i }));

    const options = screen.getAllByRole("option");
    const frOption = options.find(
      (o) => o.textContent?.includes("FR") || o.textContent?.includes("Français")
    );
    expect(frOption).toBeDefined();
    fireEvent.keyDown(frOption!, { key: " " });

    expect(i18nModule.changeLanguage).toHaveBeenCalledWith("fr");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("options are focusable (tabIndex=0)", () => {
    render(<LanguageSelector />);
    fireEvent.click(screen.getByRole("button", { name: /language|select language/i }));
    const options = screen.getAllByRole("option");
    for (const option of options) {
      expect(option).toHaveAttribute("tabindex", "0");
    }
  });
});
