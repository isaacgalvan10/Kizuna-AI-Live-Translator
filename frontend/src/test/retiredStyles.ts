// The redesign's shared DOM guard rail: jsdom has no CSS engine, so the restyle
// is pinned by what must be absent — glass blur, the retired indigo/slate/
// violet palette, Tailwind's default state hues, and white (raw or translucent).
// One deliberate exception exists in the app: the operator QR card's bare
// `bg-white` quiet zone, passed as an explicit allowance at that call site.

export const RETIRED_STYLES =
  /backdrop|indigo|slate|violet|rose-\d|amber-\d|emerald-\d|bg-white/;

// SVG elements expose className as an SVGAnimatedString, so read the attribute.
export function classNamesOf(element: Element): string {
  return element.getAttribute('class') ?? '';
}

export function retiredStyleViolations(
  container: HTMLElement,
  allowedClasses: readonly string[] = []
): string[] {
  const violations: string[] = [];
  for (const element of container.querySelectorAll('[class]')) {
    const className = classNamesOf(element);
    const retired = className
      .split(/\s+/)
      .filter((name) => !allowedClasses.includes(name) && RETIRED_STYLES.test(name));
    if (retired.length > 0) {
      violations.push(
        `${element.tagName.toLowerCase()} still wears retired styles (${retired.join(', ')}): ${className}`
      );
    }
  }
  return violations;
}
