import { useEffect } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(ScrollTrigger);

/**
 * Fades + lifts every element matching `selector` on the page into place
 * once as it enters the viewport. One shared timing/easing so every scroll
 * reveal in the app moves the same way instead of a grab-bag of ad hoc
 * effects. Deliberately page-wide (not scoped to a single container ref) so
 * it works uniformly across every section of a page without each one
 * needing to remember to wire up its own ref.
 */
export function useScrollReveal(selector = ".scroll-reveal", options = {}) {
  useEffect(() => {
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const targets = document.querySelectorAll(selector);
    if (!targets.length) return undefined;

    if (reduceMotion) {
      gsap.set(targets, { opacity: 1, y: 0 });
      return undefined;
    }

    const triggers = [];
    targets.forEach((el, i) => {
      const tween = gsap.to(el, {
        opacity: 1,
        y: 0,
        duration: 0.9,
        ease: "power3.out",
        delay: options.stagger ? (i % (options.staggerGroup || 1)) * options.stagger : 0,
        scrollTrigger: {
          trigger: el,
          start: "top 88%",
          toggleActions: "play none none none",
        },
      });
      if (tween.scrollTrigger) triggers.push(tween.scrollTrigger);
    });

    // Elements can shift after fonts/images finish loading; make sure
    // trigger positions reflect final layout rather than a transient one.
    const refresh = () => ScrollTrigger.refresh();
    window.addEventListener("load", refresh);

    return () => {
      window.removeEventListener("load", refresh);
      triggers.forEach((t) => t.kill());
    };
  }, [selector, options.stagger, options.staggerGroup]);
}
