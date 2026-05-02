/**
 * Mock for html2canvas — used in test environment only.
 */
export default function html2canvas(
  _element: HTMLElement,
  _options?: Record<string, unknown>
): Promise<HTMLCanvasElement> {
  const canvas = document.createElement("canvas");
  canvas.toDataURL = () => "data:image/png;base64,mock";
  return Promise.resolve(canvas);
}
