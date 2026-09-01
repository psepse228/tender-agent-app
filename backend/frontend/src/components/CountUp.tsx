import { useEffect, useRef } from 'react';
import { animate, useMotionValue, useTransform } from 'motion/react';

interface CountUpProps {
  value: number;
  suffix?: string;
  className?: string;
}

/** Animates a dashboard number counting up to its new value instead of
 * snapping straight to it -- same small "dashboard feels alive" touch
 * Argus/TD Webster use for stat tiles. Respects prefers-reduced-motion by
 * just jumping straight to the target. */
export function CountUp({ value, suffix = '', className }: CountUpProps) {
  const motionValue = useMotionValue(0);
  const rounded = useTransform(motionValue, (v) => `${Math.round(v)}${suffix}`);
  const ref = useRef<HTMLSpanElement>(null);
  const prevValue = useRef(0);

  useEffect(() => {
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const controls = animate(motionValue, value, {
      duration: reduceMotion ? 0 : 0.7,
      ease: [0.2, 0.7, 0.3, 1],
    });
    prevValue.current = value;
    return () => controls.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  useEffect(() => {
    const unsubscribe = rounded.on('change', (v) => {
      if (ref.current) ref.current.textContent = v;
    });
    return unsubscribe;
  }, [rounded]);

  return (
    <span ref={ref} className={className}>
      0{suffix}
    </span>
  );
}
