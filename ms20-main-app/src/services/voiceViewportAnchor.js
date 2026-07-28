function scrollable(element, view) {
  if (!element || element === view?.document?.body) return false;
  const style = view?.getComputedStyle?.(element);
  const overflow = `${style?.overflow || ""} ${style?.overflowY || ""} ${style?.overflowX || ""}`;
  return /(auto|scroll|overlay)/.test(overflow);
}

export function createVoiceViewportAnchor(root, { cardId, field }, view = window) {
  const selector = `[data-catalog-edit-field="${CSS.escape(field)}"][data-card-id="${CSS.escape(cardId)}"]`;
  const target = root?.querySelector?.(selector);
  if (!target) return null;
  const scrollPositions = [];
  for (let element = target.parentElement; element && element !== root; element = element.parentElement) {
    if (scrollable(element, view)) {
      scrollPositions.push({
        id: element.id || "",
        cardId: element.dataset?.cardId || "",
        className: element.className || "",
        top: element.scrollTop,
        left: element.scrollLeft
      });
    }
  }
  return {
    cardId,
    field,
    selector,
    top: target.getBoundingClientRect().top,
    windowX: view.scrollX || 0,
    windowY: view.scrollY || 0,
    selectionStart: target.selectionStart,
    selectionEnd: target.selectionEnd,
    scrollPositions
  };
}

function findScrollContainer(root, saved) {
  if (saved.id) return root.querySelector(`#${CSS.escape(saved.id)}`);
  if (saved.cardId) return root.querySelector(`[data-card-id="${CSS.escape(saved.cardId)}"]`);
  if (typeof saved.className === "string" && saved.className.trim()) {
    const classes = saved.className.trim().split(/\s+/).map((name) => `.${CSS.escape(name)}`).join("");
    return root.querySelector(classes);
  }
  return null;
}

export function restoreVoiceViewportAnchor(root, anchor, view = window, { restoreFocus = true } = {}) {
  if (!anchor) return false;
  const target = root?.querySelector?.(anchor.selector);
  if (!target) return false;
  view.scrollTo?.(anchor.windowX, anchor.windowY);
  anchor.scrollPositions.forEach((saved) => {
    const element = findScrollContainer(root, saved);
    if (element) {
      element.scrollTop = saved.top;
      element.scrollLeft = saved.left;
    }
  });
  if (restoreFocus) target.focus?.({ preventScroll: true });
  if (restoreFocus && Number.isInteger(anchor.selectionStart) && Number.isInteger(anchor.selectionEnd)) {
    target.setSelectionRange?.(anchor.selectionStart, anchor.selectionEnd);
  }
  const delta = target.getBoundingClientRect().top - anchor.top;
  if (Math.abs(delta) > 1) view.scrollBy?.(0, delta);
  return true;
}
