import { AnimatePresence, motion, useDragControls } from 'motion/react';
import type { ReactNode } from 'react';
import { CloseIcon } from './icons';

interface BottomSheetProps {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}

/** The Тендеры screen's swipe-down-to-dismiss detail sheet (renderStatsHtml
 * in the old vanilla frontend). Framer Motion replaces the old CSS
 * transform/opacity transitions with the same easing curve. */
export function BottomSheet({ open, onClose, children }: BottomSheetProps) {
  // Scopes the actual drag gesture to just the handle's own pointerdown
  // (dragListener=false on the sheet itself) instead of the whole sheet
  // area -- keeps a `drag`-enabled surface from ever being confused with
  // "everything in here reacts to a light finger movement", which is what
  // made the close button and any content inside read as unreliable to
  // tap on a real touchscreen (a mouse-simulated click doesn't reproduce
  // that the same way, which is why this didn't show up in earlier
  // headless testing).
  const dragControls = useDragControls();

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className="sheet-overlay"
            onClick={onClose}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
          />
          <motion.div
            className="sheet"
            initial={{ y: '100%' }}
            animate={{ y: 0, transition: { type: 'spring', damping: 34, stiffness: 340 } }}
            // Closing reads as unresponsive if it lingers or bounces --
            // a quick, decisive tween here (not the bouncier entrance
            // spring) so tapping close feels instant.
            exit={{ y: '100%', transition: { duration: 0.2, ease: [0.4, 0, 1, 1] } }}
            drag="y"
            dragListener={false}
            dragControls={dragControls}
            dragConstraints={{ top: 0, bottom: 0 }}
            // Elastic resistance is applied to the *reported* drag offset
            // too, not just the visual rubber-band -- too much of it means
            // even a real full-length swipe never crosses the close
            // threshold below. 0.92 keeps a token bit of resistance (so it
            // still reads as "grabbing the sheet") while letting a real
            // swipe actually close it.
            dragElastic={{ top: 0, bottom: 0.92 }}
            onDragEnd={(_, info) => {
              if (info.offset.y > 70 || info.velocity.y > 350) onClose();
            }}
          >
            <div className="sheet-handle-hitzone" onPointerDown={(e) => dragControls.start(e)}>
              <div className="sheet-handle" />
            </div>
            <button className="sheet-close-btn press" onClick={onClose} title="Закрыть" aria-label="Закрыть">
              <CloseIcon />
            </button>
            <div className="sheet-body">{children}</div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
