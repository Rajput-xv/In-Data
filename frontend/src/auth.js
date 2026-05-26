// Tiny session-scoped "auth".
//
// Not real auth - we compare the entered email against VITE_ANALYST_EMAIL
// from the env. If it matches, we remember it in sessionStorage so the
// three protected pages can read it and the API client can stamp it
// onto every X-Analyst-Email header.
//
// sessionStorage (not localStorage) means closing the tab logs out.
// That's the cheapest "stay signed in for the demo, don't persist for
// the next visitor" behaviour I can ship.

const STORAGE_KEY = "indata.analyst.email";

export function expectedEmail() {
  return (import.meta.env.VITE_ANALYST_EMAIL || "").trim().toLowerCase();
}

export function getEmail() {
  try {
    return sessionStorage.getItem(STORAGE_KEY) || "";
  } catch {
    return "";
  }
}

export function setEmail(email) {
  try {
    sessionStorage.setItem(STORAGE_KEY, email);
  } catch {
    /* private mode etc - login just won't persist past a refresh */
  }
}

export function clearEmail() {
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    /* nothing to do */
  }
}

export function isAuthed() {
  return getEmail().length > 0;
}
