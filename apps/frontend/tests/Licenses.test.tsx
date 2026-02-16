import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import Licenses from "../src/pages/Licenses";

describe("Licenses Component", () => {
  it("renders page title", () => {
    render(
      <BrowserRouter>
        <Licenses />
      </BrowserRouter>
    );
    expect(screen.getByText(/Open-Source Lizenzen/i)).toBeInTheDocument();
  });

  it("renders frontend dependencies", () => {
    render(
      <BrowserRouter>
        <Licenses />
      </BrowserRouter>
    );
    expect(screen.getByText("React", { exact: true })).toBeInTheDocument();
    expect(screen.getByText(/Framer Motion/i)).toBeInTheDocument();
  });

  it("renders backend dependencies", () => {
    render(
      <BrowserRouter>
        <Licenses />
      </BrowserRouter>
    );
    expect(screen.getByText(/FastAPI/i)).toBeInTheDocument();
  });

  it("renders compliance notice", () => {
    render(
      <BrowserRouter>
        <Licenses />
      </BrowserRouter>
    );
    expect(screen.getByText(/Lizenz-Compliance/i)).toBeInTheDocument();
  });

  it("renders attribution section", () => {
    render(
      <BrowserRouter>
        <Licenses />
      </BrowserRouter>
    );
    expect(screen.getByText(/Danksagung/i)).toBeInTheDocument();
  });
});
