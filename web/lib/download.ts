import { toast } from "sonner";

/**
 * Fetch a generated file and hand it to the browser, or say why it isn't there.
 *
 * A plain `<a href>` to the API is less code and was what this used to be, but
 * generated resumes expire (app/db/retention.py) and the download endpoints
 * purge before they read. So a button that was valid when the page rendered can
 * be dead by the time it is clicked, and the tab then navigates off the app
 * onto FastAPI's raw {"detail": "pdf not found"} — a 404 with no way back.
 *
 * Fetching first keeps that failure inside the page, where it can be a sentence
 * about what happened instead of a status code.
 */
export async function downloadFile(url: string, filename: string): Promise<void> {
  let res: Response;
  try {
    res = await fetch(url);
  } catch {
    toast.error("Could not reach the backend. Is it still running?");
    return;
  }

  if (res.status === 404) {
    toast.error(
      "That resume has expired — generated resumes are kept for a few minutes. Generate it again.",
    );
    return;
  }
  if (!res.ok) {
    toast.error(`Could not download the file (${res.status}).`);
    return;
  }

  const href = URL.createObjectURL(await res.blob());
  const link = document.createElement("a");
  link.href = href;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(href);
}
